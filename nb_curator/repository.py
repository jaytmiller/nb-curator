"""Repository management for cloning and updating notebook repositories."""

import shutil
import tempfile
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

    def run(self, *args, **keys):
        return self.env_manager.curator_run(*args, **keys)

    def handle_result(self, *args, **keys):
        return self.env_manager.handle_result(*args, **keys)

    def setup_repos(self, repo_urls: list[str], single_branch=True) -> bool:
        """set up all specified repositories."""
        self.logger.debug(f"Setting up repos. urls={repo_urls}.")
        for repo_url in repo_urls:
            repo_path = self._setup_remote_repo(repo_url, single_branch=single_branch)
            if not repo_path:
                return False
        return True

    def _repo_path(self, repo_url: str) -> Path:
        """Get the path for a repository."""
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        return self.repos_dir / repo_name

    def _setup_remote_repo(
        self, repo_url: str, single_branch: bool = True
    ) -> Optional[Path]:
        """set up a remote repository by cloning or updating."""
        repo_path = self._repo_path(repo_url)
        if repo_path.exists():
            self.logger.info(f"Using existing local clone at {repo_path}")
            return repo_path
        else:
            try:
                return self._clone_repo(
                    repo_url, repo_path, single_branch=single_branch
                )
            except Exception as e:
                self.logger.exception(e, f"Failed to setup repository {repo_url}.")
                return None

    def _clone_repo(self, repo_url: str, repo_dir: Path, single_branch=True) -> Path:
        """Clone a new repository."""
        single_branch = "--single-branch" if single_branch else ""
        self.logger.info(
            f"Cloning {single_branch} repository {repo_url} to {repo_dir}."
        )
        if self.env_manager is None:
            raise RuntimeError("Environment manager not available")
        self.run(
            f"git clone {single_branch} {repo_url} {str(repo_dir)}",
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

    def is_clean(self, repo_root: str | Path) -> bool:
        stats: str = self.run("git status --porcelain", check=True, cwd=repo_root)
        stats = "clean" if stats == "" else "dirty"
        self.logger.debug(f"Repo '{repo_root}' status is: {stats}.")
        return stats == "clean"

    def branch_repo(
        self, repo_name: str, new_branch: str, ingest_branch: str = "origin/main"
    ) -> bool:
        repo_root = self.repos_dir / repo_name
        if not repo_root.exists():
            return self.logger.error(f"Can't branch non-existent repo {repo_name}.")
        if not self.is_clean(repo_root):
            return self.logger.error(f"Won't branch dirty repo {repo_name}.")
        self.logger.debug(
            f"Branching {repo_name} from {ingest_branch} to {new_branch}."
        )
        if not self.git_checkout(repo_name, ingest_branch):
            return False
        if not self.git_create_branch(repo_name, new_branch):
            return False
        return True

    def git_checkout(self, repo_name: str, branch: str) -> bool:
        repo_root = self.repos_dir / repo_name
        result = self.run(f"git checkout {branch}", check=False, cwd=repo_root)
        return self.handle_result(
            result,
            f"Failed checking out repo {repo_name} existing branch {branch}: ",
            f"Checked out repo {repo_name} existing branch {branch}.",
        )

    def git_create_branch(self, repo_name, new_branch):
        repo_root = self.repos_dir / repo_name
        result = self.run(f"git checkout -b {new_branch}", check=False, cwd=repo_root)
        return self.handle_result(
            result,
            f"Failed creating new branch {new_branch} of repo {repo_name}: ",
            f"Created new branch {new_branch} of repo {repo_name}.",
        )

    def git_add(self, repo_name: str, path_to_add: str | Path) -> bool:
        path_to_add = str(path_to_add)
        repo_root = self.repos_dir / repo_name
        result = self.run(f"git add {path_to_add}", check=False, cwd=repo_root)
        return self.handle_result(
            result,
            f"Failed adding {path_to_add} from {repo_name}: ",
            f"Added {path_to_add} to {repo_name}.",
        )

    def git_commit(self, repo_name: str, commit_msg: str) -> bool:
        repo_root = self.repos_dir / repo_name
        with tempfile.NamedTemporaryFile(mode="w+") as temp:
            temp.write(commit_msg)
            temp.flush()
            result = self.run(f"git commit -F {temp.name}", check=False, cwd=repo_root)
            return self.handle_result(
                result,
                f"Failed commiting {repo_name}: ",
                f"Commited {repo_name}.",
            )

    def git_push(self, repo_name: str, branch_name: str) -> bool:
        repo_root = self.repos_dir / repo_name
        result = self.run(f"git push origin {branch_name}", check=False, cwd=repo_root)
        return self.handle_result(
            result,
            f"Failed pushing repo {repo_name} branch {branch_name}: ",
            f"Pushed repo {repo_name} branch {branch_name}.",
        )

    def github_create_pr(
        self, repo_name: str, merge_to: str, title: str, body_msg: str
    ) -> bool:
        repo_root = self.repos_dir / repo_name
        with tempfile.NamedTemporaryFile(mode="w+") as temp:
            temp.write(body_msg)
            temp.flush()
            result = self.run(
                (
                    "gh",
                    "pr",
                    "create",
                    # "--base",
                    # merge_to,
                    "--no-maintainer-edit",
                    "--title",
                    "'" + title + "'",
                    "--body-file",
                    temp.name,
                ),
                check=False,
                cwd=repo_root,
            )
            return self.handle_result(
                result,
                f"Failed creating PR {title} for {repo_name}: ",
                f"Created PR {title} to {merge_to} for {repo_name}.",
            )

    def github_merge_pr(
        self, repo_name: str, merge_from: str, title: str, body_msg: str
    ) -> bool:
        repo_root = self.repos_dir / repo_name
        with tempfile.NamedTemporaryFile(mode="w+") as temp:
            temp.write(body_msg)
            temp.flush()
            result = self.run(
                (
                    "gh",
                    "pr",
                    "merge",
                    merge_from,
                    "--rebase",
                    "-t",
                    "'" + title + "'",
                    "--body-file",
                    temp.name,
                ),
                check=False,
                cwd=repo_root,
            )
            return self.handle_result(
                result,
                f"Failed merging PR {title} to {repo_name}: ",
                f"Merged PR {title} to {repo_name}.",
            )
