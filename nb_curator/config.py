"""Configuration management for nb-curator."""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class CuratorConfig:
    """Configuration class for NotebookCurator."""
    
    spec_file: str
    python_program: str = sys.executable
    revise_spec_file: bool = False
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
    clone: bool = False
    
    def __post_init__(self):
        """Post-initialization processing."""
        self.output_dir = Path(self.output_dir)
        self.repos_dir = (
            Path(self.repos_dir) if self.repos_dir 
            else Path.cwd() / "notebook-repos"
        )