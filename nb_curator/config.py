"""Configuration management for nb-curator."""

import os.path
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_MICROMAMBA_PATH = os.environ.get("NBC_MM", "") + "/bin/" + "micromamba"


@dataclass
class CuratorConfig:
    """Configuration class for NotebookCurator."""

    spec_file: str

    micromamba_path: str = "micromamba"
    output_dir: Path = Path("./output")
    verbose: bool = False
    debug: bool = False

    repos_dir: Optional[Path] = None
    clone_repos: bool = False
    delete_repos: bool = False

    init_env: bool = False
    delete_env: bool = False

    compile_packages: bool = False
    install_packages: bool = False
    uninstall_packages: bool = False

    test_notebooks: str | None = None
    jobs: int = 1
    timeout: int = 300

    inject_spi: bool = False
    submit_for_build: bool = False

    reset_spec: bool = False

    curate: bool = False

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
