"""Configuration management for nb-curator."""

import sys
import os.path
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class CuratorConfig:
    """Configuration class for NotebookCurator."""

    spec_file: str
    micromamba_path: str = "micromamba"
    output_dir: str = "./output"
    repos_dir: Optional[str] = None
    verbose: bool = False
    debug: bool = False
    cleanup: bool = False
    compile: bool = False
    no_simplify_paths: bool = False
    install: bool = False
    test: bool = False
    jobs: int = 1
    timeout: int = 300
    environment: str = "base"
    init_env: bool = False
    wipe_env: bool = False
    clone: bool = None
    inject_spi: bool = False

    def __post_init__(self):
        """Post-initialization processing."""
        self.output_dir = Path(self.output_dir)
        self.repos_dir = (
            Path(self.repos_dir) if self.repos_dir else Path.cwd() / "repos"
        )

    @property
    def spec_file_out(self) -> Path:
        """Output path for the spec file."""
        return self.output_dir / os.path.basename(self.spec_file)
