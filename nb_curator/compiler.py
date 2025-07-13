"""Requirements compilation and dependency resolution."""

import subprocess
from pathlib import Path
from typing import List, Optional

from .logging import CuratorLogger

# from ruamel.yaml import YAML

class RequirementsCompiler:
    """Compiles and resolves package requirements."""

    def __init__(
        self,
        logger: CuratorLogger,
        env_manager: EnvironmentManager,
        python_path: str = sys.executable,
        python_version: str,
    ):
        self.logger = logger
        self.env_manager = env_manager
        self.python_path = python_path
        self.python_version = python_version

    def find_requirements_files(self, notebook_paths: List[str]) -> List[Path]:
        """Find requirements.txt files in notebook directories."""
        requirements_files = []
        notebook_dirs = {Path(nb_path).parent for nb_path in notebook_paths}
        for dir_path in notebook_dirs:
            req_file = dir_path / "requirements.txt"
            if req_file.exists():
                requirements_files.append(req_file)
                self.logger.debug(f"Found requirements file: {req_file}")

        self.logger.info(f"Found {len(requirements_files)} requirements.txt files")
        return requirements_files

    def compile_requirements(
        self, requirements_files: List[Path], output_path: Path
    ) -> Optional[List[str]]:
        """Compile requirements files into pinned versions,  outputs
        the result to a file at `output_path` and then loads the
        output and returns a list of package versions for insertion
        into other commands and specs.
        """
        if not requirements_files:
            return self.logger.warning("No requirements files to compile")
        self.logger.info("Compiling requirements to determine package versions")
        if not self._run_uv_compile(output_path, requirements_files):
            self.logger.error("========== Failed compiling requirements ==========")
            self.logger.error(self.annotated_requirements(requirements_files))
            return None
        package_versions = self.read_package_versions([output_path])
        self.logger.info(f"Resolved {len(package_versions)} package versions")
        return package_versions

    def read_package_versions(self, requirements_files: List[Path]) -> List[str]:
        """Read package versions from a list of requirements files omitting blank
        and comment lines.
        """
        package_versions = []
        for req_file in requirements_files:
            lines = self.read_package_lines(req_file)
            package_versions.extend(lines)
        return package_versions

    def read_package_lines(self, requirements_file: Path) -> List[str]:
        """Read package lines from requirements file omitting blank and comment lines.
        Should work with most forms of requirements.txt file,
        input or compiled,  and reduce it to a pure list of package versions.
        """
        lines = []
        with open(requirements_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    lines.append(line)
        return lines

    def annotated_requirements(self, requirements_files: List[Path]) -> str:
        """Create an annotated input requirements listing to correlate version
        constraints with the notebooks which impose them,  primarily as an aid
        for direct conflict resolution.   Strictly speaking this is a WIP since
        without compiling individual notebook requirements first dependencies
        are not included which can be where the real conflicts occur without
        necessarily a common root import.
        """
         result= []
        for req_file in requirements_files:
            lines =  self.read_package_lines(req_file)
            result.append([(pkgdep, str(req_file)) for pkg in lines])   # note difference
        result = sorted(result)
        return "\n".join(f"{pkg:<20}  : {path:<55}" for pkg, path in result)

    def generate_mamba_spec(self, kernel_name: str, mamba_files: List[str], output_path: Path) -> dict:
        """Generate mamba environment specification."""
        dependencies = [
                f"python={self.python_version}" if self.python_version else "3",
        ]
        spi_packages = self.read_package_versions(mamba_files)
        dependencies += spi_packages
        dependencies += [{"pip": []},]
        mamba_spec = {
            "name": kernel_name,
            "channels": ["conda-forge"],
            "dependencies": dependencies
        }
        from ruamel.yaml import YAML
        yaml = YAML()
        with output_path.open("w") as f:
            yaml.dump(mamba_spec, f)
        return spec

    def _run_uv_compile(
        self, output_file: Path, requirements_files: List[Path]
    ) -> bool:
        """Run uv pip compile command."""
        cmd = [
            "uv",
            "pip",
            "compile",
            "--output-file",
            str(output_file),
            "--python",
            self.python_path,
            "--python-version",
            self.python_version,
            "--universal",
            "--no-header",
            "--annotate",
            "--constraints",
        ] + [str(f) for f in requirements_files]

        if self.logger.verbose:
            cmd.append("--verbose")

        result = self.env_manager.curator_run(cmd, check=False)
        return self.handle_result(result, f"uv compile failed:")

