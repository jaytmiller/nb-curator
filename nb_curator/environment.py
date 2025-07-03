"""Environment management for package installation and testing."""

import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from .logging import CuratorLogger


CURATOR_PACKAGES = [
    "uv", "mamba", "papermill", "ipykernel"
]


class EnvironmentManager:
    """Manages Python environment setup and package installation."""
    
    def __init__(self, logger: CuratorLogger, python_program: str = sys.executable):
        self.logger = logger
        self.python_program = python_program
    
    def initialize_environment(self, environment_name: str = "base") -> bool:
        """Initialize the environment for notebook processing."""
        self.logger.info("Initializing environment...")
        
        # Install curator packages
        if not self._install_curator_packages():
            return False
        
        # Register Jupyter environment
        if not self._register_environment(environment_name):
            return False
        
        self.logger.info("Environment initialization completed successfully")
        return True
    
    def check_python_version(self, requested_version: List[int]) -> bool:
        """Check if the current Python version matches the requested version."""
        self.logger.info("Checking Python version...")
        
        result = subprocess.run(
            [self.python_program, "--version"],
            capture_output=True, text=True, check=True
        )
        
        system_version = list(map(int, result.stdout.strip().split()[-1].split(".")))
        
        for i, version in enumerate(requested_version):
            if version != system_version[i]:
                return self.logger.error(
                    f"Environment running Python {system_version} but "
                    f"Python {requested_version} is requested"
                )
        
        return True
    
    def install_packages(self, package_versions: List[str], output_dir: Path, 
                        moniker: str) -> bool:
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
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            self.logger.error(f"Package installation failed: {result.stderr}")
            return False
        
        self.logger.info("Package installation completed successfully")
        return True
    
    def test_imports(self, import_map: dict) -> bool:
        """Test package imports."""
        self.logger.info(f"Testing {len(import_map)} imports")
        failed_imports = []
        
        for pkg in import_map:
            if pkg.startswith("#"):
                continue
            
            try:
                __import__(pkg)
                self.logger.info(f"Importing {pkg} ... ok")
            except Exception:
                self.logger.error(f"Failed to import {pkg}")
                failed_imports.append(pkg)
        
        if failed_imports:
            self.logger.error(f"Failed to import {len(failed_imports)} packages: {failed_imports}")
            return False
        
        self.logger.info("All imports succeeded")
        return True
    
    def _install_curator_packages(self) -> bool:
        """Install required curator packages."""
        cmd = ["pip", "install"] + CURATOR_PACKAGES
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return self.logger.error(f"Failed to install curator packages: {result.stderr}")
        
        return True
    
    def _register_environment(self, environment_name: str) -> bool:
        """Register Jupyter environment for the environment."""
        cmd = [
            self.python_version, "-m", "ipykernel", "install", 
            "--user", "--name", environment_name
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return self.logger.error(f"Failed to register environment: {result.stderr}")
        
        return True