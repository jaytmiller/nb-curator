from .logging import CuratorLogger
from pathlib import Path
from typing import List, Optional

# from ruamel.yaml import YAML


def get_injector(logger: CuratorLogger, repos_dir: str) -> "SpiInjector":
    """
    Factory method to create an instance of an SpiInjector which is tuned to
    configure an SPI deployment based on a curator spec.
    """
    return SpiInjector(logger, repos_dir)


class SpiInjector:
    """
    A placeholder class for injecting the Science Platform Images (SPI) respository.
    """

    url = "https://github.com/spacetelescope/science-platform-images.git"
    repo_name = "science-platform-images"

    def __init__(self, logger: CuratorLogger, repos_dir: str):
        self.logger = logger
        self.repos_dir = repos_dir
        self.spi_path = Path(repos_dir) / self.repo_name

    def inject(self, full_spec: dict) -> None:
        """
        Performs a placeholder injection of the SPI.
        In a real implementation, this would gather information about
        the Python environment, installed packages, Jupyter kernels, etc.
        """
        self.logger.info(
            f"Initiating SPI injection into {self.spi_path} for {self.deployment_name} kernel {self.kernel_name}..."
        )
        self._inject(full_spec["out"], "curated_repository_urls", self.kernel_path)
        self._inject(full_spec["out"], "mamba_spec", self.env_yml)
        self._inject(full_spec["out"], "package_versions", self.env_pip)
        self._inject(full_spec["out"], "test_imports", self.test_path / "imports")
        self._inject(full_spec["out"], "test_notebooks", self.test_path / "notebooks")
        self.logger.info("SPI injection complete.")

    def _inject(self, full_spec: dict, field: str, where: str) -> None:
        from ruamel.yaml import YAML
        self.logger.info(f"Injecting field {field} to {where}")
        with open(str(where), "w") as f:
            obj = full_spec[field]
            if isinstance(obj, dict):
                yaml = YAML(typ='unsafe', pure=True)
                yaml.dump(obj, f)
            elif isinstance(obj, list):
                f.write("\n".join(obj))
            elif isinstance(obj, str):
                f.write(obj)
            else:
                raise ValueError(f"Unsupported type {type(obj)} for field {field}")

    def get_spi_requirements(self, glob_patterns: List[Path], kind:str) -> List[Path]:
        """Find extra mamba or pip requirements files required by SPI environments such as those
        included in the common/common-env directory. mamba packages are typically non-Python packages
        such as C libraries and compiles and install tools.  For Python packages,  using
        pip to install them is preferred.
        """
        spi_extra_requirements = []
        for pattern in glob_patterns:
            extras = Path(".").glob(str(pattern))
            spi_extra_requirements.extend(list(extras))
            self.logger.debug(f"Found SPI extra {kind} requirements: {extras}")
        self.logger.info(f"Found SPI extra {len(spi_extra_requirements)} {kind} .pip requirements.")
        return spi_extra_requirements

    def _init_patterns(self, deployment_name: str, kernel_name: str) -> None:
        self.deployment_name = deployment_name
        self.kernel_name = kernel_name
        self.deployments_path = self.spi_path / "deployments"
        self.deployment_path = self.deployments_path / deployment_name
        self.environments_path = self.deployment_path / "environments"
        self.kernel_path = self.environments_path / kernel_name
        self.test_path = self.kernel_path / "tests"
        self.env_pip = self.kernel_path / f"{self.kernel_name}.pip"
        self.env_yml = self.kernel_path / f"{self.kernel_name}.yml"
        self.pip_patterns = [
            self.deployments_path / "common/common-env/*.pip",
            self.kernel_path / "*.pip",
        ]
        self.mamba_patterns = [
            self.deployments_path / "common/common-env/*.conda",
            self.kernel_path / "*.conda",
        ]

    def find_spi_pip_requirements_files(self, deployment_name: str, kernel_name: str) -> List[Path]:
        self._init_patterns(deployment_name, kernel_name)
        self.env_pip.unlink(missing_ok=True)
        return self.get_spi_requirements(self.pip_patterns, "pip")

    def find_spi_mamba_requirements_files(self, deployment_name: str, kernel_name: str) -> List[Path]:
        self._init_patterns(deployment_name, kernel_name)
        self.env_yml.unlink(missing_ok=True)
        return self.get_spi_requirements(self.mamba_patterns, "mamba")
