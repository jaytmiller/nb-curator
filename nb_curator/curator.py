"""Main NotebookCurator class orchestrating the curation process."""

import os
from typing import List

from .config import CuratorConfig
from .logging import CuratorLogger
from .spec_manager import SpecManager
from .repository import RepositoryManager
from .nb_processor import NotebookProcessor
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
            self.logger,
            self.config.micromamba_path,
        )
        self.repo_manager = RepositoryManager(
            config.repos_dir, self.logger, config.clone_repos, self.env_manager
        )
        self.notebook_processor = NotebookProcessor(self.logger)
        self.tester = NotebookTester(
            self.logger, self.environment_name, config.jobs, config.timeout
        )
        self.compiler = RequirementsCompiler(self.logger, self.env_manager)
        self.injector = get_injector(self.logger, config.repos_dir, self.spec_manager)

        # Create output directories
        os.makedirs(config.output_dir, exist_ok=True)
        os.makedirs(config.repos_dir, exist_ok=True)

        # State variables
        self.repos_to_setup = {}

    @property
    def deployment_name(self):
        return self.spec_manager.deployment_name if self.spec_manager else None

    @property
    def environment_name(self):
        return self.spec_manager.kernel_name if self.spec_manager else None

    def main(self) -> bool:
        """Main execution method."""
        try:
            return self._execute_workflow()
        except Exception as e:
            return self.logger.exception(e, f"Error during curation: {e}")

    def _execute_workflow(self) -> bool:
        """Execute the complete curation workflow."""

        # Setup repositories if cloning requested.  Otherwise assume clones exist as needed
        spec_repo_urls = self.spec_manager.get_repository_urls()
        spi_repo_urls = [self.injector.url]
        repo_urls = spec_repo_urls + spi_repo_urls
        if not self.repo_manager.setup_repos(repo_urls):
            return False

        # Handle requirements compilation
        if self.config.compile_env:
            mamba_spec_outfile, pip_output_file = (
                self._handle_requirements_compilation()
            )
        test_imports = self.spec_manager.get_output_data("test_imports", [])
        notebook_paths = self.spec_manager.get_output_data("test_notebooks", [])

        # Initialize target environment if requested.
        # We assume nb-curator is running in nbcurator bootstrap environment or equivalent.
        if self.config.init_env:
            if not self.env_manager.create_environment(
                self.environment_name, mamba_spec_outfile
            ):
                return False
            if not self.env_manager.register_environment(self.environment_name):
                return False

        # Install packages if requested
        if self.config.install_env:
            if not self.env_manager.install_packages(
                package_versions,
                self.config.output_dir,
                self.spec_manager.get_moniker(),
            ):
                return False
            if not self.env_manager.test_imports(test_imports):
                return False

        # Test notebooks if requested, config.test is a regex or None, default=.*
        if self.config.test_notebooks:
            filtered_notebooks = self.tester.filter_notebooks(
                notebook_paths, self.config.test_notebooks
            )
            if not self.tester.test_notebooks(filtered_notebooks):
                return False

        if self.config.inject_spi:
            self.injector.inject()

        # Cleanup if requested
        if self.config.delete_repos:
            if not self.repo_manager.delete_repos():
                return False

        if self.config.delete_env:
            if not self.env_manager.unregister_environment(self.environment_name):
                return False
            if not self.env_manager.delete_environment(self.environment_name):
                return False

        return True

    def _handle_requirements_compilation(self) -> bool:
        """Handle requirements compilation workflow."""
        # Identify notebook paths --> notebooks, requirements, imports
        notebook_paths = self.notebook_processor.collect_notebook_paths(
            self.spec_manager.to_dict(), self.repos_to_setup
        )
        if not notebook_paths:
            return False

        # Extract imports
        test_imports = self.notebook_processor.extract_imports(notebook_paths)
        if not test_imports:
            self.log.warning(
                "No imports found in notebooks. Import tests will be skipped."
            )
        moniker = self.spec_manager.get_moniker()

        # Generate mamba spec for environment
        kernel_name = self.spec_manager.kernel_name
        mamba_spec_outfile = self.config.output_dir / f"{moniker}-mamba-spec.yml"
        mamba_files = self.injector.find_spi_mamba_requirements_files(
            self.spec_manager.deployment_name, self.spec_manager.kernel_name
        )
        mamba_spec = self.compiler.generate_mamba_spec(
            kernel_name, mamba_files, mamba_spec_outfile
        )

        # Compile requirements for pip version constraint solution
        pip_output_file = self.config.output_dir / f"{moniker}-pip-compile.txt"
        requirements_files = self.compiler.find_requirements_files(notebook_paths)
        requirements_files += self.injector.find_spi_pip_requirements_files(
            self.spec_manager.deployment_name, self.spec_manager.kernel_name
        )
        package_versions = self.compiler.compile_requirements(
            requirements_files, pip_output_file
        )
        notebook_repos = list(self.repos_to_setup)
        notebook_repos.remove(self.injector.url)

        # Store results in spec
        self.spec_manager.revise_and_save(
            package_versions=package_versions,
            mamba_spec=mamba_spec,
            pip_requirements_files=requirements_files,
            mamba_requirements_files=mamba_files,
            repository_urls=notebook_repos,
        )
        return mamba_spec_outfile, pip_output_file

    def print_log_counters(self):
        """Print summary of logged messages."""
        self.logger.print_log_counters()
