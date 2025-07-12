"""Environment management for package installation and testing."""

import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from .logging import CuratorLogger


CURATOR_PACKAGES = ["uv", "mamba", "papermill", "ipykernel", "jupyter", "setuptools"]


class EnvironmentManager:
    """Manages Python environment setup and package installation."""

    def __init__(self, logger: CuratorLogger, micromamba_path: str = "micromamba"):
        self.logger = logger
        self.micromamba_path = micromamba_path

    def run(self, command: List[str], check=True) -> Optional[str]:
        """Run a command in the current environment."""
        self.logger.debug(f"Running command: {command}")
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=check,
        )
        self.logger.debug(f"Command output: {result.stdout}")
        if check:
            return result.stdout
        else:
            return result

    def env_run(self, environment, command: List[str], check=True) -> Optional[str]:
        """Run a command in the specified environment."""
        self.logger.debug(f"Running command {command} in environment: {environment}")
        mm_prefix = [self.micromamba_path, "run", "-n", environment]
        return self.run(mm_prefix + command, check=check)

    def initialize_environment(self, environment_name: str, mamba_spec: str) -> bool:
        """Initialize the environment for notebook processing."""
        self.logger.info("Initializing environment...")

        # Create the environment
        if not self.create_environment(environment_name):
            return False

        # Install curator packages
        if not self._install_curator_packages():
            return False

        # Register Jupyter environment
        if not self._register_environment(environment_name):
            return False

        self.logger.info("Environment initialization completed successfully")
        return True

    def create_environment(self, environment_name: str, micromamba_spec: str|None = None) -> bool:
        """Create a new environment."""
        if not micromamba_spec:
            micromamba_spec = "python=3.10"
            self.logger.info(f"Creating environment: {environment_name}")
            mm_prefix = [self.micromamba_path, "create", "-n", environment_name]
            command = mm_prefix + ["-c", "conda-forge"]
            self.run(command)
        return True

    def _install_curator_packages(self) -> bool:
        """Install required curator packages."""
        self.logger.info("Installing required curator packages...")
        cmd = ["install"] + CURATOR_PACKAGES
        return self.env_run(environment, cmd)

    def delete_environment(self, environment_name: str) -> bool:
        """Delete an existing environment."""
        self.logger.info(f"Deleting environment: {environment_name}")
        mm_prefix = [self.micromamba_path, "env", "remove", "-n", environment_name]
        command = mm_prefix + ["--yes"]
        return self.run(command)

    def check_python_version(self, environment: str, requested_version: List[int]) -> bool:
        """Check if the current Python version matches the requested version."""
        self.logger.info(f"Checking Python version for environment {tess}...")

        output = subprocess.env_run(environment, ["python", "--version"])
        self.logger.info(f"Python version output: {output}")

        system_version = list(map(int, output.strip().split()[-1].split(".")))

        for i, version in enumerate(requested_version):
            if version != system_version[i]:
                return self.logger.error(
                    f"Environment running Python {system_version} but "
                    f"Python {requested_version} is requested"
                )

        return True

    def install_packages(
        self, package_versions: List[str], output_dir: Path, moniker: str
    ) -> bool:
        """Install the compiled package list."""
        if not package_versions:
            return self.logger.warning("No packages found to install")

        self.logger.info(f"Installing {len(package_versions)} packages")

        # Create temporary requirements file
        temp_req_file = output_dir / f"{moniker}-install-requirements.txt"

        with open(temp_req_file, "w") as f:
            for package in sorted(package_versions):
                f.write(f"{package}\n")

        # Install packages using uv
        cmd = ["uv", "pip", "install", "-r", str(temp_req_file)]
        result = self.env_run(environment, cmd, check=False)

        if result.returncode != 0:
            self.logger.error(f"Package installation failed: {result.stderr}")
            return False

        self.logger.info("Package installation completed successfully:", "\n" + result.stdout)
        return True

    def test_imports(self, import_map: dict) -> bool:
        """Test package imports."""
        self.logger.info(f"Testing {len(import_map)} imports")
        failed_imports = []

        for pkg in import_map:
            if pkg.startswith("#"):
                continue

            try:
                self.logger.info(f"Importing {pkg} ...")
                __import__(pkg)
                self.logger.info(f"Importing {pkg} ... ok")
            except Exception as exc:
                self.logger.exception(exc, f"Failed to import {pkg}")
                failed_imports.append(pkg)

        if failed_imports:
            self.logger.error(
                f"Failed to import {len(failed_imports)} packages: {failed_imports}"
            )
            return False

        self.logger.info("All imports succeeded")
        return True

    def _register_environment(self, environment_name: str) -> bool:
        """Register Jupyter environment for the environment.

        nbcurator environment should work here since it is modifying 
        files under $HOME related to *any* jupyter environment the 
        user has.
        """
        cmd = [
            "python",
            "-m",
            "ipykernel",
            "install",
            "--user",
            "--name",
            environment_name,
            "--display-name",
            environment_name,
        ]
        result = self.run(cmd, check=False)
        if result.returncode != 0:
            return self.logger.error(f"Failed to register environment {environment_name}: {result.stderr}")

        return True

    def _unregister_environment(self, environment_name: str) -> bool:
        """Unregister Jupyter environment for the environment."""

        cmd = [
            "jupyter",
            "kernelspec",
            "uninstall",
            environment_name,
        ]
        result = self.run(cmd, check=False)
        if result.returncode != 0:
            return self.logger.error(f"Failed to unregister environment {environment_name}: {result.stderr}")
