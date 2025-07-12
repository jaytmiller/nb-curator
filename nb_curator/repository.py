"""Repository management for cloning and updating notebook repositories."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional

from .logging import CuratorLogger


class RepositoryManager:
    """Manages git repository operations for notebook collections.
    
    
    """

    def __init__(self, repos_dir: Path, logger: CuratorLogger, clone: bool = False):
        self.repos_dir = repos_dir
        self.logger = logger
        self.clone = clone
        self.repos_to_setup: Dict[str, Optional[Path]] = {}

    def setup_repositories(self, repo_urls: list[str]) -> bool:
        """Set up all specified repositories."""
        self.repos_to_setup = {url: None for url in repo_urls}
        for repo_url in repo_urls:
            if not self.clone:
                if repo_url.startswith("file://"):
                    repo_url = repo_url.replace("file://", "")
                repo_path = self._setup_local_repo(repo_url)
            else:
                repo_path = self._setup_remote_repo(repo_url)
            if not repo_path:
                return False
            self.repos_to_setup[repo_url] = repo_path
        return True

    def _setup_local_repo(self, repo_url: str) -> Optional[Path]:
        """Set up a local repository."""
        local_path = Path(os.path.expanduser(repo_url[7:]))  # Remove "file://"
        if not local_path.exists():
            self.logger.error(f"Local repository path does not exist: {local_path}")
            return None
        self.logger.info(f"Using local repository at {local_path}")
        return local_path

    def _setup_remote_repo(self, repo_url: str) -> Optional[Path]:
        """Set up a remote repository by cloning or updating."""
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        repo_dir = self.repos_dir / repo_name
        if not self.clone:
            if repo_dir.exists():
                self.logger.info(f"Using existing repository at {repo_dir}")
                return repo_dir
            else:
                self.logger.error(
                    f"Repository not found and cloning disabled: {repo_dir}"
                )
                return None
        return self._clone_or_update_repo(repo_url, repo_dir)

    def _clone_or_update_repo(self, repo_url: str, repo_dir: Path) -> Optional[Path]:
        """Clone or update a repository."""
        try:
            if repo_dir.exists():
                return self._update_repo(repo_dir)
            else:
                return self._clone_repo(repo_url, repo_dir)
        except Exception as e:
            self.logger.exception(e, f"Failed to setup repository {repo_url}")
            return None

    def _update_repo(self, repo_dir: Path) -> Path:
        """Update an existing repository."""
        self.logger.info(f"Updating repository at {repo_dir}")
        try:
            subprocess.run(
                ["git", "-C", str(repo_dir), "pull"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.logger.info(f"Successfully updated repository at {repo_dir}")
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"Failed to update repository: {e.stderr}")
            self.logger.warning("Continuing with existing version")
        return repo_dir

    def _clone_repo(self, repo_url: str, repo_dir: Path) -> Path:
        """Clone a new repository."""
        self.logger.info(f"Cloning repository {repo_url} to {repo_dir}")
        subprocess.run(
            ["git", "clone", "--single-branch", repo_url, str(repo_dir)],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.logger.info(f"Successfully cloned repository to {repo_dir}")
        return repo_dir

    def cleanup_repos(self) -> bool:
        """Clean up cloned repositories."""
        try:
            if self.repos_dir.exists():
                self.logger.info(f"Cleaning up repository directory: {self.repos_dir}")
                shutil.rmtree(self.repos_dir)
                return True
        except Exception as e:
            return self.logger.exception(e, f"Error during cleanup: {e}")
