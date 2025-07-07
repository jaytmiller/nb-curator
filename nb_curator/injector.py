from .logging import CuratorLogger

from ruamel import yaml


def get_injector(logger: CuratorLogger, where: str | None) -> "SpiInjector":
    """
    Factory method to create an instance of an SpiInjector which is tuned to
    configure an SPI deployment based on a curator spec.
    """
    if where is None:
        return None
    return SpiInjector(logger, where)


class SpiInjector:
    """
    A placeholder class for injecting the Science Platform Images (SPI) respository.
    """

    url = "https://github.com/spacetelescope/science-platform-images.git"

    def __init__(self, logger: CuratorLogger):
        self.logger = logger
        self.deployment_name = deployment_name

    def inject(
        self, full_spec: dict, spi_path: str, deployment: str, kernel: str
    ) -> None:
        """
        Performs a placeholder injection of the SPI.
        In a real implementation, this would gather information about
        the Python environment, installed packages, Jupyter kernels, etc.
        """
        self.logger.info(
            f"Initiating SPI injection for {deployment_name} kernel {kernel_name}..."
        )
        environments = f"{spi_path}/deployments/{deployment_name}/environments"
        kernel_path = f"{environments}/{kernel_name}"
        test_path = f"{kernel_path}/test"
        self._inject(
            full_spec["conda"],
        )
        self.logger.info("SPI injection complete.")

    def _inject(self, field: Any, where: str) -> None:
        with open(where, "w") as f:
            yaml.dump(field, f)

    def _inject_conda(self, conda_spec: str) -> None:
        pass

    def _inject_pip(self, pip_spec: str) -> None:
        pass

    def _inject_notebooks(self, notebooks: str) -> None:
        pass

    def _inject_imports(self, imports: str) -> None:
        pass
