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

    def curator_run(self, command: List[str], check=True, timeout=300, capture_output=True, text=True) -> Optional[str] | subprocess.CompetedProcess:
        """Run a command in the current environment."""
        self.logger.debug(f"Running command: {command}")
        result = subprocess.run(
            command,
            capture_output=capture_output,
            text=capture_output,
            check=check,
            timeout=timeout,
        )
        self.logger.debug(f"Command output: {result.stdout}")
        if check:
            return result.stdout
        else:
            return result

    def handle_result(self, result: subprocess.CompletedProcess, fail: str, success: str = ""):
        """Provide standard handling for the check=False case of the xxx_run methods by
        issuing a success info or fail error and returning True or False respectively
        depending on the return code of a subprocess result.

        If either the success or fail log messages (stripped) end in ":" then append
        result.stdout or result.stderr respectively.
        """
        if result.returncode != 0:
            if fail.strip().endswith(":"):
                fail += result.stderr
            return self.logger.error(fail)
        else:
            if success.strip().endswith(":"):
                success += result.stdout
            return self.logger.info(success) if success else True


    def env_run(self, environment, command: List[str], **keys) -> Optional[str]:
        """Run a command in the specified environment.
        
        See EnvironmentManager.run for **keys optional settings.
        """
        self.logger.debug(f"Running command {command} in environment: {environment}")
        mm_prefix = [self.micromamba_path, "run", "-n", environment]
        return self.curator_run(mm_prefix + command, **keys)

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

        return self.logger.info("Environment initialization completed successfully")

    def create_environment(self, environment_name: str, micromamba_spec: str|None = None) -> bool:
        """Create a new environment."""
        if not micromamba_spec:
            micromamba_spec = "python=3.10"
            self.logger.info(f"Creating environment: {environment_name}")
            mm_prefix = [self.micromamba_path, "create", "-n", environment_name]
            command = mm_prefix + ["-c", "conda-forge"]
            self.curator_run(command)
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
        return self.curator_run(command)

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
        return self.handle_result(result,
            "Package installation failed:",
            "Package installation completed successfully:",
        )

    def test_imports(self, environment_name:str, import_map: dict) -> bool:
        """Test package imports."""
        python_imports = list(import_map.keys())
        self.logger.info(f"Testing {len(import_map)} imports")
        result = self.env_run(environment_name, ["test-imports",] + python_imports, check=False)
        return self.env_manager.handle_result(
            "Failed to import notebook packages:",
            "All imports succeeded.",
        )

    def _register_environment(self, environment_name: str, display_name=None) -> bool:
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
            display_name or environment_name,
        ]
        result = self.curator_run(cmd, check=False)
        return self.handle_result(result,
            f"Failed to register environment {environment_name}: "
        )

    def _unregister_environment(self, environment_name: str) -> bool:
        """Unregister Jupyter environment for the environment."""
        cmd = [
            "jupyter",
            "kernelspec",
            "uninstall",
            environment_name,
        ]
        result = self.curator_run(cmd, check=False)
        return self.handle_result(result,
            f"Failed to unregister environment {environment_name}: "
        )
