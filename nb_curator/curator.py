"""Main NotebookCurator class orchestrating the curation process."""

import os
from pathlib import Path
from typing import List, Optional

from .config import CuratorConfig
from .logging import CuratorLogger
from .spec_manager import SpecManager
from .repository import RepositoryManager
from .processor import NotebookProcessor
from .environment import EnvironmentManager
from .compiler import RequirementsCompiler
from .notebook_tester import NotebookTester
from .injector import get_injector


class NotebookCurator:
    """Main class orchestrating the notebook curation process."""

    def __init__(self, config: CuratorConfig):
        self.config = config
        self.logger = CuratorLogger(config.verbose, config.debug)
        self.spec_manager = SpecManager.load_and_validate(
            self.config.spec_file, self.logger
        )
        self.env_manager = EnvironmentManager(
            self.logger, self.config.micromamba_path, self.spec_manager.python_version
        )
        self.repo_manager = RepositoryManager(
            config.repos_dir, self.logger, config.clone, self.env_manager
        )
        self.notebook_processor = NotebookProcessor(self.logger)
        self.tester = NotebookTester(
            self.logger, config.environment, config.jobs, config.timeout
        )
        self.compiler = RequirementsCompiler(self.logger, self.env_manager)
        self.injector = get_injector(self.logger, config.repos_dir)

        # Create output directories
        os.makedirs(config.output_dir, exist_ok=True)
        os.makedirs(config.repos_dir, exist_ok=True)

        # State variables
        self.repos_to_setup = {}

    @property
    def deployment_name(self):
        return self.spec_manager.deployment_name if self.spec_manager else None

    @property
    def kernel_name(self):
        return self.spec_manager.kernel_name if self.spec_manager else None

    def main(self) -> bool:
        """Main execution method."""
        try:
            return self._execute_workflow()
        except Exception as e:
            return self.logger.exception(e, f"Error during curation: {e}")

    def _execute_workflow(self) -> bool:
        """Execute the complete curation workflow."""

        # Load and validate specification
        if not self._load_and_validate_spec():
            return False

        # Check Python version compatibility
        if not self._check_python_version():
            return False

        # Setup repositories if cloning requested.  Otherwise assume clones exist as needed
        spec_repo_urls = self.spec_manager.get_repository_urls()
        spi_repo_urls = self.injector.repository_urls
        repo_urls = spec_repo_urls + spi_repo_urls
        if not self._setup_repositories(repo_urls):
            return False

        # Process notebooks
        notebook_paths = self.notebook_processor.collect_notebook_paths(
            self.spec_manager.to_dict(), self.repos_to_setup
        )
        if not notebook_paths:
            return False

        # Handle requirements compilation
        if self.config.compile:
            self._handle_requirements_compilation(notebook_paths)
            # Extract imports
            test_imports = self.notebook_processor.extract_imports(notebook_paths)
            if not test_imports:
                return False
            if not self._revise_spec_file(notebook_paths, test_imports):
                return False
        else:
            test_imports = self.spec_manager.get_output_data("test_imports", {})
            notebook_paths = self.spec.get_output_data("test_notebooks", {})

        # Initialize target environment if requested;  we assume nb-curator is running in nbcurator bootstrap environment or equivalent
        if self.config.init_target_environment:
            if not self.env_manager.initialize_environment(
                self.config.environment, self.micromamba_path
            ):
                return False

        # Install packages if requested
        if self.config.install:
            if not self._install_and_test_packages(test_imports):
                return False

        # Test notebooks if requested
        if self.config.test:
            if not self._test_notebooks(notebook_paths):
                return False

        if self.config.inject_spi:
            self.injector.inject(self.spec_manager.to_dict())

        # Cleanup if requested
        if self.config.cleanup:
            if not self.repo_manager.cleanup_repos():
                return False

        return True

    def _load_and_validate_spec(self) -> bool:
        """Load and validate the specification file."""
        return self.spec_manager is not None

    def _check_python_version(self) -> bool:
        """Check Python version compatibility."""
        requested_version = self.spec_manager.get_python_version_list()
        return self.env_manager.check_python_version(requested_version)

    def _handle_requirements_compilation(self, notebook_paths: List[str]) -> bool:
        """Handle requirements compilation workflow."""
        requirements_files = compiler.find_requirements_files(notebook_paths)
        requirements_files += self.injector.find_spi_pip_requirements_files(
            self.spec_manager.deployment_name, self.spec_manager.kernel_name
        )
        mamba_files = []
        mamba_files += self.injector.find_spi_mamba_requirements_files(
            self.spec_manager.deployment_name, self.spec_manager.kernel_name
        )

        # Generate mamba spec for environment
        kernel_name = self.spec_manager.kernel_name
        mamba_spec_outfile = self.config.output_dir / f"{kernel_name}.yml"
        mamba_spec = compiler.generate_mamba_spec(
            kernel_name, mamba_files, mamba_spec_outfile
        )

        # Compile requirements
        pip_output_file = (
            self.config.output_dir
            / f"{self.spec_manager.get_moniker()}-compile-output.txt"
        )
        package_versions = compiler.compile_requirements(
            requirements_files, pip_output_file
        )

        if not package_versions:
            return False

        # Store results in spec
        self.spec_manager.set_output_data("package_versions", package_versions)
        self.spec_manager.set_output_data("mamba_spec", mamba_spec)
        self.spec_manager.set_output_data(
            "pip_requirements_files", [str(f) for f in requirements_files]
        )
        self.spec_manager.set_output_data(
            "mamba_requirements_files", [str(m) for m in mamba_files]
        )
        notebook_repos = list(self.repos_to_setup)
        notebook_repos.remove(self.injector.url)
        self.spec_manager.set_output_data(
            "repository_urls", [str(r) for r in notebook_repos]
        )

        return True

    def _install_and_test_packages(self, test_imports: dict) -> bool:
        """Install packages and test imports."""
        package_versions = self.spec.get("out", {}).get("package_versions", [])

        if not self.env_manager.install_packages(
            package_versions, self.config.output_dir, self._get_moniker()
        ):
            return False

        return self.env_manager.test_imports(test_imports)

    def _test_notebooks(self, notebook_paths: List[str]) -> bool:
        """Test notebooks based on configuration."""
        if isinstance(self.config.test, str):
            filtered_notebooks = self.tester.filter_notebooks(
                notebook_paths, self.config.test
            )
        else:
            filtered_notebooks = notebook_paths

        return self.tester.test_notebooks(filtered_notebooks)

    def _get_moniker(self) -> str:
        """Get a filesystem-safe version of the image name."""
        return self.spec["image_spec_header"]["image_name"].replace(" ", "-").lower()

    def print_log_counters(self):
        """Print summary of logged messages."""
        self.logger.print_log_counters()
