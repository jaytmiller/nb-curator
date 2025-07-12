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
        micromamba_path: str,
        python_version: str,
    ):
        self.logger = logger
        self.micromamba_path = micromamba_path
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
        """Compile requirements files into pinned versions."""
        if not requirements_files:
            return self.logger.warning("No requirements files to compile")

        self.logger.info("Compiling requirements to determine package versions")

        # Writes out a requirements.txt file with pinned versions to output_path
        if not self._run_uv_compile(output_path, requirements_files):
            self.logger.error("========== Failed compiling requirements ==========")
            self.logger.error(self._annotated_requirements(requirements_files))
            return None

        package_versions = self.read_package_versions([output_path])

        self.logger.info(f"Resolved {len(package_versions)} package versions")
        return package_versions

    def read_package_versions(self, requirements_files: List[Path]) -> List[str]:
        """Read package versions from requirements files."""
        # Read compiled requirements
        package_versions = []
        for req_file in requirements_files:
            with req_file.open("r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        package_versions.append(line)
        return package_versions

    def _annotated_requirements(self, requirements_files: List[Path]) -> str:
        """Create annotated requirements listing."""
        result = []
        for req_file in requirements_files:
            with open(req_file, "r") as f:
                for pkgdep in f.read().splitlines():
                    if pkgdep and not pkgdep.startswith("#"):
                        result.append((pkgdep, str(req_file)))   # note difference

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
            "--no-header",
            "--mamba_program",
            self.mamba_program,
            "--python-version",
            self.python_version,
            "--annotate",
        ] + [str(f) for f in requirements_files]

        if self.logger.verbose:
            cmd.append("--verbose")

        result = self.(cmd, check=False)

        if result.returncode != 0:
            self.logger.error(f"uv compile failed: {result.stderr}")
            return False

        return True

