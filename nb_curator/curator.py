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
    
        # Setup repositories
        notebook_repo_urls = self.spec_manager.get_repository_urls()
        repo_urls = notebook_repo_urls + [self.injector.url]
    
        if not self.repo_manager.setup_repos(self.config.clone_repos, repo_urls):
            return False

        # Handle requirements compilation or ensure files exist
        if self.config.compile_env:
            if not self._compile_requirements(notebook_repo_urls):
                return False
        else:
            self._ensure_output_files_exist()

        # Get file paths (guaranteed to exist now)
        mamba_spec_outfile = self.spec_manager.get_output_data("mamba_spec_outfile", None)
        pip_output_file = self.spec_manager.get_output_data("pip_output_file", None)
        test_imports = self.spec_manager.get_output_data("test_imports", [])
        notebook_paths = self.spec_manager.get_output_data("test_notebooks", [])

        # Environment operations
        if self.config.init_env:
            if not self._initialize_environment(mamba_spec_outfile):
                return False

        if self.config.install_env:
            if not self._install_packages(pip_output_file, test_imports):
                return False

        # Testing
        if self.config.test_notebooks:
            if not self._test_notebooks(notebook_paths):
                return False

        # Cleanup operations
        if self.config.inject_spi:
            self.injector.inject()

        if self.config.delete_repos:
            if not self.repo_manager.delete_repos():
                return False

        if self.config.delete_env:
            if not self._cleanup_environment():
                return False

        return True

    def _compile_requirements(self, notebook_repo_urls: List[str]) -> bool:
        """Compile requirements and update spec."""
        # Collect notebooks and extract imports
        notebook_paths = self.spec_manager.collect_notebook_paths(
            self.config.repos_dir, notebook_repo_urls
        )
        if not notebook_paths:
            return False

        test_imports = self.notebook_import_processor.extract_imports(notebook_paths)
        if not test_imports:
            self.logger.warning("No imports found in notebooks. Import tests will be skipped.")

        # Generate mamba spec
        mamba_spec_outfile, mamba_spec = self._generate_mamba_spec(notebook_repo_urls)
    
        # Generate pip requirements
        pip_output_file, package_versions, requirements_files = self._generate_pip_requirements(notebook_paths)
    
        # Update spec with all results
        self.spec_manager.revise_and_save(
            output_dir=self.config.output_dir,
            package_versions=package_versions,
            mamba_spec=mamba_spec,
            pip_requirements_files=requirements_files,
            mamba_requirements_files=self.injector.find_spi_mamba_requirements_files(),
            notebook_repo_urls=notebook_repo_urls,
            injector_url=self.injector.url,
            test_imports=test_imports,
            test_notebooks=notebook_paths,
            mamba_spec_outfile=str(mamba_spec_outfile),
            pip_output_file=str(pip_output_file),
        )
    
        return True

    def _initialize_environment(self, mamba_spec_outfile: str) -> bool:
        """Initialize the target environment."""
        if not self.env_manager.create_environment(self.environment_name, mamba_spec_outfile):
            return False
        return self.env_manager.register_environment(self.environment_name)

    def _install_packages(self, pip_output_file: str, test_imports: List[str]) -> bool:
        """Install packages and test imports."""
        if not self.env_manager.install_packages(self.environment_name, [pip_output_file]):
            return False
        return self.env_manager.test_imports(self.environment_name, test_imports)

    def _test_notebooks(self, notebook_paths: List[str]) -> bool:
        """Test notebooks matching the configured pattern."""
        filtered_notebooks = self.tester.filter_notebooks(
            notebook_paths, self.config.test_notebooks
        )
        return self.tester.test_notebooks(filtered_notebooks)

    def _cleanup_environment(self) -> bool:
        """Clean up the test environment."""
        self.env_manager.unregister_environment(self.environment_name)
        return self.env_manager.delete_environment(self.environment_name)

    def _ensure_output_files_exist(self):
        """Ensure mamba spec and pip requirements files exist on filesystem from spec data."""
        mamba_spec_outfile = self.spec_manager.get_output_data("mamba_spec_outfile", None)
        pip_output_file = self.spec_manager.get_output_data("pip_output_file", None)
        
        # Recreate files from spec if they don't exist
        if mamba_spec_outfile and not os.path.exists(mamba_spec_outfile):
            mamba_spec = self.spec_manager.get_output_data("mamba_spec", {})
            self.compiler.write_mamba_spec_file(mamba_spec_outfile, mamba_spec)
        
        if pip_output_file and not os.path.exists(pip_output_file):
            package_versions = self.spec_manager.get_output_data("package_versions", {})
            self.compiler.write_pip_requirements_file(pip_output_file, package_versions)

    def _generate_mamba_spec(self, notebook_repo_urls: List[str]) -> str:
        """Generate mamba environment specification."""
        moniker = self.spec_manager.get_moniker()
        kernel_name = self.spec_manager.kernel_name
        mamba_spec_outfile = self.config.output_dir / f"{moniker}-mamba-spec.yml"
        mamba_files = self.injector.find_spi_mamba_requirements_files()
        
        mamba_spec = self.compiler.generate_mamba_spec(
            kernel_name, mamba_files, mamba_spec_outfile
        )
        
        return mamba_spec_outfile, mamba_spec

    def _generate_pip_requirements(self, notebook_paths: List[str]) -> tuple:
        """Generate pip requirements compilation."""
        moniker = self.spec_manager.get_moniker()
        pip_output_file = self.config.output_dir / f"{moniker}-pip-compile.txt"
        
        requirements_files = self.compiler.find_requirements_files(notebook_paths)
        requirements_files += self.injector.find_spi_pip_requirements_files()
        
        package_versions = self.compiler.compile_requirements(
            requirements_files, pip_output_file
        )
        
        return pip_output_file, package_versions, requirements_files

    def print_log_counters(self):
        """Print summary of logged messages."""
        self.logger.print_log_counters()
