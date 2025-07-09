"""Main NotebookCurator class orchestrating the curation process."""

import os
import shutil
from pathlib import Path
from typing import List, Optional

from .config import CuratorConfig
from .logging import CuratorLogger
from .spec_validator import SpecValidator
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

        # Initialize components
        self.validator = SpecValidator(self.logger)
        self.repo_manager = RepositoryManager(
            config.repos_dir, self.logger, config.clone
        )
        self.notebook_processor = NotebookProcessor(self.logger)
        self.env_manager = EnvironmentManager(self.logger, config.python_program)
        self.tester = NotebookTester(
            self.logger, config.environment, config.jobs, config.timeout
        )
        self.injector = get_injector(self.logger, config.repos_dir)

        # Create output directories
        os.makedirs(config.output_dir, exist_ok=True)
        os.makedirs(config.repos_dir, exist_ok=True)

        # State variables
        self.spec = {}
        self.repos_to_setup = {}

    @property
    def deployment_name(self):
        return self.spec["image_spec_header"]["deployment_name"]

    @property
    def kernel_name(self):
        return self.spec["image_spec_header"]["kernel_name"]

    def main(self) -> bool:
        """Main execution method."""
        try:
            return self._execute_workflow()
        except Exception as e:
            return self.logger.exception(e, f"Error during curation: {e}")

    def _execute_workflow(self) -> bool:
        """Execute the complete curation workflow."""
        # Initialize environment if requested
        if self.config.init_env:
            if not self.env_manager.initialize_environment(self.config.environment):
                return False

        # Load and validate specification
        if not self._load_and_validate_spec():
            return False

        # Check Python version compatibility
        if not self._check_python_version():
            return False

        # Setup repositories
        if not self._setup_repositories():
            return False

        # Process notebooks
        notebook_paths = self.notebook_processor.collect_notebook_paths(
            self.spec, self.repos_to_setup
        )
        if not notebook_paths:
            return False

        # Handle requirements compilation
        if self._handle_requirements_compilation(notebook_paths):
            # Extract imports
            test_imports = self.notebook_processor.extract_imports(notebook_paths)
            if not test_imports:
                return False
            if not self._revise_spec_file(notebook_paths, test_imports):
                return False
        else:
            return False

        # Install packages if requested; test imports implied
        if self.config.install:
            if not self._install_and_test_packages(test_imports):
                return False

        # Test notebooks if requested
        if self.config.test:
            if not self._test_notebooks(notebook_paths):
                return False

        if self.config.inject_spi:
            self.injector.inject(
                self.spec
            )

        # Cleanup if requested
        if self.config.cleanup:
            if not self.repo_manager.cleanup_repos():
                return False

        return True

    def _load_and_validate_spec(self) -> bool:
        """Load and validate the specification file."""
        if not self.validator.load_spec(self.config.spec_file):
            return False

        if not self.validator.validate_spec():
            return False

        self.spec = self.validator.spec
        return True

    def _check_python_version(self) -> bool:
        """Check Python version compatibility."""
        requested_version = self._get_requested_python_version()
        return self.env_manager.check_python_version(requested_version)

    def _get_requested_python_version(self) -> List[int]:
        """Extract requested Python version from spec."""
        version_str = self.spec["image_spec_header"]["python_version"]
        if isinstance(version_str, (int, float)):
            version_str = str(version_str)
        if not isinstance(version_str, str):
            raise ValueError("Invalid python_version in spec file")
        return list(map(int, version_str.split(".")))

    def _setup_repositories(self) -> bool:
        """Setup all required repositories."""
        # Collect repository URLs
        repo_urls = [self.spec["image_spec_header"]["nb_repo"]]

        for entry in self.spec["selected_notebooks"]:
            nb_repo = entry.get("nb_repo", repo_urls[0])
            if nb_repo not in repo_urls:
                repo_urls.append(nb_repo)
        repo_urls.append(self.injector.url)
        # Setup repositories
        if not self.repo_manager.setup_repositories(repo_urls):
            return False

        self.repos_to_setup = self.repo_manager.repos_to_setup
        return True

    def _handle_requirements_compilation(self, notebook_paths: List[str]) -> bool:
        """Handle requirements compilation workflow."""
        compiler = RequirementsCompiler(
            self.logger,
            self.config.python_program,
            str(self.spec["image_spec_header"]["python_version"]),
            self.config.verbose,
        )

        requirements_files = compiler.find_requirements_files(notebook_paths)
        requirements_files += self.injector.find_spi_pip_requirements_files(
            self.deployment_name, self.kernel_name
        )

        if self.config.compile:
            # Compile requirements
            output_file = (
                self.config.output_dir / f"{self._get_moniker()}-compile-output.txt"
            )
            package_versions = compiler.compile_requirements(
                requirements_files, output_file
            )

            if not package_versions:
                return False

            mamba_files = []
            mamba_files += self.injector.find_spi_mamba_requirements_files(
                self.deployment_name, self.kernel_name
            )
            # Generate mamba spec
            mamba_spec = compiler.generate_mamba_spec(
                self.spec["image_spec_header"]["image_name"],
                mamba_files,
            )

            # Store results in spec
            if "out" not in self.spec:
                self.spec["out"] = {}

            self.spec["out"]["package_versions"] = package_versions
            self.spec["out"]["mamba_spec"] = mamba_spec
            self.spec["out"]["pip_requirements_files"] = [str(f) for f in requirements_files]
            self.spec["out"]["mamba_requirements_files"] = [str(m) for m in mamba_files]

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

    def _revise_spec_file(self, notebook_paths: List[str], test_imports: dict) -> bool:
        """Update the spec file with computed outputs."""
        try:
            self.logger.info(f"Revising spec file {self.config.spec_file} --> {self.config.spec_file_out}")

            # Update spec with outputs
            if "out" not in self.spec:
                self.spec["out"] = {}

            self.spec["out"]["test_notebooks"] = [str(p) for p in notebook_paths]
            self.spec["out"]["test_imports"] = list(test_imports.keys())

            # Write updated spec
            from ruamel.yaml import YAML

            yaml = YAML()
            yaml.preserve_quotes = True
            yaml.indent(mapping=2, sequence=4, offset=2)

            with open(self.config.spec_file_out, "w") as f:
                yaml.dump(self.spec, f)

            return self.logger.info(f"Revised spec file written to {self.config.spec_file_out}")
        except Exception as e:
            return self.logger.exception(e, f"Error revising spec file: {e}")

    def _get_moniker(self) -> str:
        """Get a filesystem-safe version of the image name."""
        return self.spec["image_spec_header"]["image_name"].replace(" ", "-").lower()

    def print_log_counters(self):
        """Print summary of logged messages."""
        self.logger.print_log_counters()
