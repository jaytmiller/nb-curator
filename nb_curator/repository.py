"""Repository management for cloning and updating notebook repositories."""

import shutil
from pathlib import Path
from typing import Optional

from .logger import CuratorLogger
from .environment import EnvironmentManager
from .constants import REPO_CLONE_TIMEOUT


class RepositoryManager:
    """Manages git repository operations for notebook collections."""

    def __init__(
        self,
        logger: CuratorLogger,
        repos_dir: Path,
        env_manager: EnvironmentManager | None = None,
    ):
        self.repos_dir = repos_dir
        self.logger = logger
        self.env_manager = env_manager

    def setup_repos(self, repo_urls: list[str]) -> bool:
        """set up all specified repositories."""
        self.logger.debug(f"Setting up repos. urls={repo_urls}.")
        for repo_url in repo_urls:
            repo_path = self._setup_remote_repo(repo_url)
            if not repo_path:
                return False
        return True

    def _repo_path(self, repo_url: str) -> Path:
        """Get the path for a repository."""
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        return self.repos_dir / repo_name

    def _setup_remote_repo(self, repo_url: str) -> Optional[Path]:
        """set up a remote repository by cloning or updating."""
        repo_path = self._repo_path(repo_url)
        if repo_path.exists():
            self.logger.info(f"Using existing local clone at {repo_path}")
            return repo_path
        else:
            try:
                return self._clone_repo(repo_url, repo_path)
            except Exception as e:
                self.logger.exception(e, f"Failed to setup repository {repo_url}.")
                return None

    def _clone_repo(self, repo_url: str, repo_dir: Path) -> Path:
        """Clone a new repository."""
        self.logger.info(f"Cloning repository {repo_url} to {repo_dir}.")
        if self.env_manager is None:
            raise RuntimeError("Environment manager not available")
        self.env_manager.curator_run(
            ["git", "clone", "--single-branch", repo_url, str(repo_dir)],
            check=True,
            timeout=REPO_CLONE_TIMEOUT,
        )
        self.logger.info(f"Successfully cloned repository to {repo_dir}.")
        return repo_dir

    def delete_repos(self) -> bool:
        """Clean up cloned repositories."""
        try:
            if self.repos_dir.exists():
                self.logger.info(f"Deleting repository directory: {self.repos_dir}.")
                shutil.rmtree(self.repos_dir)
            return True
        except Exception as e:
            return self.logger.exception(e, "Error during repository deletion.")
