"""Main NotebookCurator class orchestrating the curation process."""

import os
from typing import List

from .config import CuratorConfig
from .logging import CuratorLogger
from .spec_manager import SpecManager
from .repository import RepositoryManager
from .nb_processor import NotebookImportProcessor
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
            self.logger,
            self.config.spec_file,
        )
        self.env_manager = EnvironmentManager(
            self.logger,
            self.config.micromamba_path,
        )
        self.repo_manager = RepositoryManager(
            self.logger, config.repos_dir, self.env_manager
        )
        self.notebook_import_processor = NotebookImportProcessor(self.logger)
        self.tester = NotebookTester(
            self.logger, self.env_manager, config.jobs, config.timeout
        )
        self.compiler = RequirementsCompiler(self.logger, self.env_manager)
        self.injector = get_injector(self.logger, config.repos_dir, self.spec_manager)

        # Create output directories
        os.makedirs(config.output_dir, exist_ok=True)
        os.makedirs(config.repos_dir, exist_ok=True)

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

        # Regardless of which steps are selected below, we can recompute
        # repo_urls always as a matter of simplicity.
        notebook_repo_urls = self.spec_manager.get_repository_urls()
        repo_urls = notebook_repo_urls + [self.injector.url]

        # Setup repositories if cloning requested.  Otherwise verify clones exist as needed,
        # since most or all steps below require these to be available.
        if not self.repo_manager.setup_repos(self.config.clone_repos, repo_urls):
            return False

        # Handle requirements compilation
        if self.config.compile_env:
            self._handle_requirements_compilation(notebook_repo_urls)

        # By fetching these from the revised spec, we ensure that they're defined
        # here even if we're not recompiling. This enables us to use a completed
        # spec for installation, testing, and subsequent steps.
        mamba_spec_outfile = self.spec_manager.get_output_data(
            "mamba_spec_outfile", None
        )
        pip_output_file = self.spec_manager.get_output_data("pip_output_file", None)
        test_imports = self.spec_manager.get_output_data("test_imports", [])
        notebook_paths = self.spec_manager.get_output_data("test_notebooks", [])
        package_versions = self.spec_manager.get_output_data("package_versions", {})

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
                self.environment_name, [pip_output_file]
            ):
                return False
            if not self.env_manager.test_imports(self.environment_name, test_imports):
                return False

        # Test notebooks if requested, config.test_notebooks is a regex or None, default=.* (all)
        if self.config.test_notebooks:
            filtered_notebooks = self.tester.filter_notebooks(
                notebook_paths, self.config.test_notebooks
            )
            if not self.tester.test_notebooks(filtered_notebooks):
                return False

        # Inject the computed outputs of the spec into a clone of the build environment.
        if self.config.inject_spi:
            self.injector.inject()

        # Delete all repos (and config.repo_dir) if requested to clean up.
        if self.config.delete_repos:
            if not self.repo_manager.delete_repos():
                return False

        # Delete test/spec environment if requested, leave the nb-curator base environment alone.
        if self.config.delete_env:
            if not self.env_manager.unregister_environment(self.environment_name):
                return False
            if not self.env_manager.delete_environment(self.environment_name):
                return False

        return True

    def _handle_requirements_compilation(self, notebook_repo_urls: List[str]) -> bool:
        """Handle requirements compilation workflow."""
        # Identify notebook paths --> notebooks, requirements, imports
        notebook_paths = self.spec_manager.collect_notebook_paths(
            self.config.repos_dir, notebook_repo_urls
        )
        if not notebook_paths:
            return False

        # Extract imports
        test_imports = self.notebook_import_processor.extract_imports(notebook_paths)
        if not test_imports:
            self.logger.warning(
                "No imports found in notebooks. Import tests will be skipped."
            )

        moniker = self.spec_manager.get_moniker()

        # Generate mamba spec for environment
        kernel_name = self.spec_manager.kernel_name
        mamba_spec_outfile = self.config.output_dir / f"{moniker}-mamba-spec.yml"
        mamba_files = self.injector.find_spi_mamba_requirements_files()
        mamba_spec = self.compiler.generate_mamba_spec(
            kernel_name, mamba_files, mamba_spec_outfile
        )

        # Compile requirements for pip version constraint solution
        pip_output_file = self.config.output_dir / f"{moniker}-pip-compile.txt"
        requirements_files = self.compiler.find_requirements_files(notebook_paths)
        requirements_files += self.injector.find_spi_pip_requirements_files()
        package_versions = self.compiler.compile_requirements(
            requirements_files, pip_output_file
        )

        # Store results in spec
        self.spec_manager.revise_and_save(
            output_dir=self.config.output_dir,
            package_versions=package_versions,
            mamba_spec=mamba_spec,
            pip_requirements_files=requirements_files,
            mamba_requirements_files=mamba_files,
            notebook_repo_urls=notebook_repo_urls,
            injector_url=self.injector.url,
            test_imports=test_imports,
            test_notebooks=notebook_paths,
        )
        return mamba_spec_outfile, pip_output_file, package_versions

    def print_log_counters(self):
        """Print summary of logged messages."""
        self.logger.print_log_counters()
