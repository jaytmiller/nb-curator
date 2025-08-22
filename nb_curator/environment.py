"""Environment management for package installation and testing.

The basic model is that micromamba is used to bootstrap and manage
both the curation and target environments.

micromamba is used to install only pre-required mamba packages.
uv is used to manage pip packages in the target environment.

environmentsinstall non-pip Python packages
"""

import os
import json
import shutil
import shlex
import subprocess
from subprocess import CompletedProcess
from pathlib import Path
from typing import Any


from .logger import CuratorLogger
from .constants import NBC_ROOT, NBC_PANTRY
from .constants import (
    DEFAULT_TIMEOUT,
    ENV_CREATE_TIMEOUT,
    INSTALL_PACKAGES_TIMEOUT,
    IMPORT_TEST_TIMEOUT,
)


class EnvironmentManager:
    """Manages Python environment setup and package installation."""

    # Currently limited to uv, older build tools for packages not yet
    # updated to pyproject.toml, and jupyter kernel management packages
    # ipykernel and jupyter.
    # Package definitions moved to constants.py

    # IMPORTANT: see also the nb-curator bash script used for bootstrapping
    # the basic nbcurator environment and inlines the above requirements
    # for CURATOR_PACKAGES.
    # Timeout constants moved to constants.py

    # ------------------------------------------------------------------------------

    def __init__(
        self, logger: CuratorLogger, micromamba_path: str | Path = "micromamba"
    ):
        self.logger = logger
        self.micromamba_path = str(micromamba_path)
        self.nbc_pantry_dir.mkdir(exist_ok=True, parents=True)

    @property
    def nbc_root_dir(self) -> Path:
        return NBC_ROOT

    @property
    def nbc_mm_dir(self) -> Path:
        return NBC_ROOT / "mm"

    @property
    def nbc_pantry_dir(self) -> Path:
        return NBC_PANTRY

    @property
    def mm_envs_dir(self) -> Path:
        return self.nbc_mm_dir / "envs"

    @property
    def mm_pkgs_dir(self) -> Path:
        return self.nbc_mm_dir / "pkgs"

    @property
    def nbc_temp_dir(self) -> Path:
        return self.nbc_root_dir / "temp"

    @property
    def nbc_cache_dir(self) -> Path:
        cache_path = os.environ.get("NBC_CACHE")
        return Path(cache_path) if cache_path else self.nbc_root_dir / "cache"

    def env_archive_path(self, env_name: str, archive_format: str) -> Path:
        return self.nbc_pantry_dir / "envs" / (env_name.lower() + archive_format)

    def env_live_path(self, env_name: str) -> Path:
        return self.mm_envs_dir / env_name

    def _condition_cmd(self, cmd: list[str] | tuple[str] | str) -> list[str]:
        """Condition the command into a list of UNIX CLI 'words'.

        If command is already a string,  split it into string "words".
        If it is a list,  make sure every element is a string.
        """
        if isinstance(cmd, (list, tuple)):
            return [str(word) for word in cmd]
        elif isinstance(cmd, str):
            return shlex.split(cmd)
        else:
            raise TypeError("cmd must be a list or str")

    def curator_run(
        self,
        command: list[str] | tuple[str] | str,
        check=True,
        cwd=None,
        timeout=DEFAULT_TIMEOUT,
        text=True,
        output_mode="separate",
        **extra_parameters,
    ):  # -> str | CompletedProcess[Any] | None:
        """Run a command in the current environment."""
        command = self._condition_cmd(command)
        parameters = dict(
            text=text,
            check=check,
            cwd=str(cwd) if cwd else cwd,
            timeout=timeout,
        )
        if output_mode == "combined":
            parameters.update(
                dict(
                    capture_output=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )
            )
        elif output_mode == "separate":
            parameters.update(
                dict(
                    capture_output=True,
                )
            )
        else:
            raise ValueError(f"Invalid output_mode value: {output_mode}")
        parameters.update(extra_parameters)
        self.logger.debug(f"Running command with no shell: {command} {parameters}")
        # self.logger.debug(f"For trying it this may work anyway: {' '.join(command)}")
        result = subprocess.run(command, **parameters)
        # self.logger.debug(f"Command output: {result.stdout}")
        if check:
            return result.stdout
        else:
            return result

    def env_run(
        self, environment, command: tuple[str] | list[str] | str, **keys
    ):  # -> str | CompletedProcess[Any] | None:
        """Run a command in the specified environment.

        See EnvironmentManager.run for **keys optional settings.
        """
        command = self._condition_cmd(command)
        self.logger.debug(f"Running command {command} in environment: {environment}")
        mm_prefix = [self.micromamba_path, "run", "-n", environment]
        return self.curator_run(mm_prefix + command, **keys)

    def handle_result(
        self, result: CompletedProcess[Any] | str | None, fail: str, success: str = ""
    ):
        """Provide standard handling for the check=False case of the xxx_run methods by
        issuing a success info or fail error and returning True or False respectively
        depending on the return code of a subprocess result.

        If either the success or fail log messages (stripped) end in ":" then append
        result.stdout or result.stderr respectively.
        """
        if not isinstance(result, CompletedProcess):
            raise RuntimeError(f"Expected CompletedProcess, got {type(result)}")
        if result.returncode != 0:
            if fail.strip().endswith(":"):
                fail += result.stderr.strip() + " ::: " + result.stdout.strip()
            return self.logger.error(fail)
        else:
            if success.strip().endswith(":"):
                success += result.stdout.strip()
            return self.logger.info(success) if success else True

    def create_environment(
        self, env_name: str, micromamba_specfile: Path | None = None
    ) -> bool:
        """Create a new environment."""
        self.logger.info(f"Creating environment: {env_name}")
        mm_prefix = [self.micromamba_path, "create", "--yes", "-n", env_name]
        command = mm_prefix + ["-f", str(micromamba_specfile)]
        result = self.curator_run(command, check=False, timeout=ENV_CREATE_TIMEOUT)
        return self.handle_result(
            result,
            f"Failed to create environment {env_name}: \n",
            f"Environment {env_name} created. It needs to be registered before JupyterLab will display it as an option.",
        )

    def delete_environment(self, env_name: str) -> bool:
        """Delete an existing environment."""
        self.logger.info(f"Deleting environment: {env_name}")
        command = self.micromamba_path + " env remove --yes -n " + env_name
        result = self.curator_run(command, check=False, timeout=ENV_CREATE_TIMEOUT)
        return self.handle_result(
            result,
            f"Failed to delete environment {env_name}: \n",
            f"Environment {env_name} deleted. It's totally gone, file storage reclaimed.",
        )

    def install_packages(self, env_name: str, requirements_paths: list[Path]) -> bool:
        """Install the compiled package lists."""
        self.logger.info(
            f"Installing packages from: {[str(p) for p in requirements_paths]}"
        )

        cmd = "uv pip install"
        for path in requirements_paths:
            cmd += " -r " + str(path)

        result = self.env_run(
            env_name, cmd, check=False, timeout=INSTALL_PACKAGES_TIMEOUT
        )
        return self.handle_result(
            result,
            f"Package installation for {env_name} failed:",
            f"Package installation for {env_name} completed successfully.",
        )

    def uninstall_packages(
        self,
        env_name: str,
        requirements_paths: list[Path],
    ) -> bool:
        """Uninstall the compiled package lists."""
        self.logger.info(
            f"Uninstalling packages from: {[str(p) for p in requirements_paths]}"
        )

        cmd = "uv pip uninstall"
        for path in requirements_paths:
            cmd += " -r " + str(path)

        # Install packages using uv
        result = self.env_run(
            env_name, cmd, check=False, timeout=INSTALL_PACKAGES_TIMEOUT
        )
        return self.handle_result(
            result,
            f"Package un-installation of {env_name} failed:",
            f"Package un-installation of {env_name} completed successfully.",
        )

    def register_environment(self, env_name: str, display_name=None) -> bool:
        """Register Jupyter environment for the environment.

        nbcurator environment should work here since it is modifying
        files under $HOME related to *any* jupyter environment the
        user has.
        """
        cmd = self._condition_cmd(
            f"python -m ipykernel install --user --name {env_name} --display-name "
        )
        cmd += [
            display_name or env_name
        ]  # display name may be multi-word,  string splits break quoting
        result = self.env_run(env_name, cmd, check=False)
        return self.handle_result(
            result,
            f"Failed to register environment {env_name} as a jupyter kernel: ",
            f"Registered environment {env_name} as a jupyter kernel making it visible to JupyterLab.",
        )

    def unregister_environment(self, env_name: str) -> bool:
        """Unregister Jupyter environment for the environment."""
        cmd = f"jupyter kernelspec uninstall -y {env_name}"
        result = self.curator_run(cmd, check=False)
        return self.handle_result(
            result,
            f"Failed to unregister Jupyter kernel {env_name}: ",
            f"Unregistered Jupyter kernel {env_name}. Environment {env_name} still exists but is no longer offered by JupyterLab.",
        )

    def environment_exists(self, env_name: str) -> bool:
        """Return True IFF `env_name` exists."""
        cmd = self.micromamba_path + " env list --json"
        try:
            result = self.curator_run(cmd, check=True)
        except Exception as e:
            return self.logger.exception(
                e,
                f"Checking for existence of environment '{env_name}' completely failed. See README.md for info on bootstrapping.",
            )
        if result is None:
            return self.logger.error("No result returned from environment check")
        result_str = result.stdout if hasattr(result, "stdout") else str(result)
        envs = json.loads(result_str)["envs"]
        for env in envs:
            self.logger.debug(f"Checking existence of {env_name} against {env}.")
            if env.endswith(env_name):
                self.logger.debug(f"Environment {env_name} exists.")
                return True
        self.logger.debug(f"Environment {env_name} does not exist.")
        return False

    def archive(self, archive_filepath: Path, source_dirpath: Path) -> bool:
        archive_filepath.parent.mkdir(parents=True, exist_ok=True)
        cmd = f"tar -acf {archive_filepath} {source_dirpath.name}"
        result = self.curator_run(cmd, cwd=source_dirpath.parent, check=False)
        return self.handle_result(
            result,
            f"Failed to pack {source_dirpath} into {archive_filepath}:",
            f"Packed {source_dirpath} into {archive_filepath}",
        )

    def unarchive(self, archive_filepath: Path, destination_dirpath: Path) -> bool:
        destination_dirpath.mkdir(parents=True, exist_ok=True)
        cmd = f"tar -axf {archive_filepath} {destination_dirpath.name}"
        result = self.curator_run(cmd, cwd=destination_dirpath.parent, check=False)
        return self.handle_result(
            result,
            f"Failed to unpack {archive_filepath} into {destination_dirpath}: ",
            f"Unpacked {archive_filepath} into {destination_dirpath}",
        )

    def pack_environment(self, env_name: str, archive_format: str) -> bool:
        return self.archive(
            self.env_archive_path(env_name, archive_format),
            self.env_live_path(env_name),
        )

    def unpack_environment(self, env_name: str, archive_format: str) -> bool:
        return self.unarchive(
            self.env_archive_path(env_name, archive_format),
            self.env_live_path(env_name),
        )

    def pack_curator(self, archive_filepath: Path | str) -> bool:
        archive_path = Path(archive_filepath)
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        return self.archive(archive_path, self.nbc_root_dir)

    def unpack_curator(self, archive_filepath: Path | str) -> bool:
        archive_path = Path(archive_filepath)
        return self.unarchive(archive_path, self.nbc_root_dir)

    def compact(self) -> bool:
        try:
            if self.mm_pkgs_dir.exists():
                shutil.rmtree(str(self.mm_pkgs_dir))
            if self.nbc_cache_dir.exists():
                shutil.rmtree(str(self.nbc_cache_dir))
            if self.nbc_temp_dir.exists():
                shutil.rmtree(str(self.nbc_temp_dir))
            self.logger.info(
                "Curator compacted successfully, removing install caches, etc."
            )
            return True
        except Exception as e:
            return self.logger.exception(e, f"Failed to compact curator: {e}")

    def test_imports(self, env_name: str, imports: list[str]) -> bool:
        """Test package imports."""
        self.logger.info(f"Testing {len(imports)} imports")
        failed_imports = []
        for import_ in imports:
            self.logger.debug(f"Testing import: {import_}")
            result = self.env_run(
                env_name,
                f"python -c 'import {import_}'",
                check=False,
                timeout=IMPORT_TEST_TIMEOUT,
            )
            succeeded = self.handle_result(
                result,
                f"Failed to import {import_}:",
                f"Import of {import_} succeeded.",
            )
            if not succeeded:
                failed_imports.append(import_)
        if failed_imports:
            return self.logger.error(
                f"Failed to import {len(failed_imports)}: {failed_imports}"
            )
        else:
            return self.logger.info("All imports succeeded.")
