from pathlib import Path
from typing import List

from .logging import CuratorLogger
from .spec_manager import SpecManager
from .utils import get_yaml


def get_injector(
    logger: CuratorLogger, repos_dir: str, spec_manager: SpecManager
) -> "SpiInjector":
    """
    Factory method to create a subclass of a Injector which is tuned to
    configure an science-platform-images deployment based on a curator spec.

    Conceptually another subclass of Injector could be created to inject into
    a different image building system.
    """
    return SpiInjector(logger, repos_dir, spec_manager)


class SpiInjector:
    """
    A class for injecting the Science Platform Images (SPI) respository.
    """

    url = "https://github.com/spacetelescope/science-platform-images.git"
    repo_name = "science-platform-images"

    def __init__(
        self, logger: CuratorLogger, repos_dir: str, spec_manager: SpecManager
    ):
        self.logger = logger
        self.repos_dir = repos_dir
        self.spi_path = Path(repos_dir) / self.repo_name
        self.spec_manager = spec_manager

    def _init_patterns(self) -> None:
        self.deployment_name = self.spec_manager.deployment_name
        self.kernel_name = self.spec_manager.kernel_name
        self.deployments_path = self.spi_path / "deployments"
        self.deployment_path = self.deployments_path / self.deployment_name
        self.environments_path = self.deployment_path / "environments"
        self.kernel_path = self.environments_path / self.kernel_name
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

    def inject(self) -> None:
        """
        Performs a placeholder injection of the SPI.
        In a real implementation, this would gather information about
        the Python environment, installed packages, Jupyter kernels, etc.
        """
        self._init_patterns()
        self.logger.info(
            f"Initiating SPI injection into {self.spi_path} for {self.deployment_name} kernel {self.kernel_name}..."
        )
        self._inject("notebook_repo_urls", self.environments_path / "notebook-repos")
        self._inject("mamba_spec", self.env_yml)
        self._inject("package_versions", self.env_pip)
        self._inject("test_imports", self.test_path / "imports")
        self._inject("test_notebooks", self.test_path / "notebooks")
        self.logger.info("SPI injection complete.")

    def _inject(self, field: str, where: str | Path) -> None:
        self.logger.info(f"Injecting field {field} to {where}")
        with open(str(where), "w") as f:
            obj = self.spec_manager.get_output_data(field)
            if isinstance(obj, dict):
                get_yaml().dump(obj, f)
            elif isinstance(obj, list):
                f.write("\n".join(obj))
            elif isinstance(obj, str):
                f.write(obj)
            else:
                raise ValueError(f"Unsupported type {type(obj)} for field {field}")

    def get_spi_requirements(self, glob_patterns: List[Path], kind: str) -> List[Path]:
        """Find extra mamba or pip requirements files required by SPI environments such as those
        included in the common/common-env directory. mamba packages are typically non-Python packages
        such as C libraries and compiles and install tools.  For Python packages,  using
        pip to install them is preferred.
        """
        spi_extra_requirements = []
        for pattern in glob_patterns:
            extras = Path(".").glob(str(pattern))
            for path in extras:
                spi_extra_requirements.append(path)
                self.logger.debug(f"Found SPI {kind} requirements file {path} based on glob '{pattern}'")
        self.logger.info(
            f"Found SPI extra {len(spi_extra_requirements)} {kind} requirements files."
        )
        return spi_extra_requirements

    def find_spi_pip_requirements_files(self) -> List[Path]:
        self._init_patterns()
        self.env_pip.unlink(missing_ok=True)
        return self.get_spi_requirements(self.pip_patterns, "pip")

    def find_spi_mamba_requirements_files(self) -> List[Path]:
        self._init_patterns()
        self.env_yml.unlink(missing_ok=True)
        return self.get_spi_requirements(self.mamba_patterns, "mamba")
