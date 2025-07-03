"""Requirements compilation and dependency resolution."""

import subprocess
from pathlib import Path
from typing import List, Optional

from .logging import CuratorLogger


class RequirementsCompiler:
    """Compiles and resolves package requirements."""
    
    def __init__(self, logger: CuratorLogger, python_program: str, 
                 python_version: str, verbose: bool = False):
        self.logger = logger
        self.python_program = python_program
        self.python_version = python_version
        self.verbose = verbose
    
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
    
    def compile_requirements(self, requirements_files: List[Path], 
                           output_file: Path) -> Optional[List[str]]:
        """Compile requirements files into pinned versions."""
        if not requirements_files:
            return self.logger.warning("No requirements files to compile")
        
        self.logger.info("Compiling requirements to determine package versions")
        
        if not self._run_uv_compile(output_file, requirements_files):
            self._log_compilation_failure(requirements_files)
            return None
        
        # Read compiled requirements
        package_versions = []
        with open(output_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    package_versions.append(line)
        
        self.logger.info(f"Resolved {len(package_versions)} package versions")
        return package_versions
    
    def generate_conda_spec(self, image_name: str) -> dict:
        """Generate conda environment specification."""
        moniker = image_name.replace(" ", "-").lower()
        
        return {
            "name": moniker,
            "channels": ["conda-forge"],
            "dependencies": [
                f"python={self.python_version}" if self.python_version else "python",
                "pip",
                {"pip": {}},
            ],
        }
    
    def _run_uv_compile(self, output_file: Path, requirements_files: List[Path]) -> bool:
        """Run uv pip compile command."""
        cmd = [
            "uv", "pip", "compile",
            "--output-file", str(output_file),
            "--no-header",
            "--python", self.python_program,
            "--python-version", self.python_version,
            "--annotate",
        ] + [str(f) for f in requirements_files]
        
        if self.verbose:
            cmd.append("--verbose")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            self.logger.error(f"uv compile failed: {result.stderr}")
            return False
        
        return True
    
    def _log_compilation_failure(self, requirements_files: List[Path]):
        """Log detailed information about compilation failure."""
        self.logger.error("========== Failed compiling requirements ==========")
        self.logger.error(self._annotated_requirements(requirements_files))
    
    def _annotated_requirements(self, requirements_files: List[Path]) -> str:
        """Create annotated requirements listing."""
        result = []
        for req_file in requirements_files:
            with open(req_file, "r") as f:
                for pkgdep in f.read().splitlines():
                    if pkgdep and not pkgdep.startswith("#"):
                        result.append((pkgdep, str(req_file)))
        
        result = sorted(result)
        return "\n".join(f"{pkg:<20}  : {path:<55}" for pkg, path in result)