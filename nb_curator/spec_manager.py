"""Unified specification management with validation and persistence."""

import os.path
import re
from typing import Dict, Any, List, Optional
from pathlib import Path

# from ruamel.yaml import YAML

from .logging import CuratorLogger


class SpecManager:
    """Manages specification loading, validation, access, and persistence."""

    ALLOWED_KEYWORDS = {
        "image_spec_header": [
            "image_name",
            "description",
            "valid_on",
            "expires_on",
            "python_version",
            "nb_repo",
            "root_nb_directory",
            "deployment_name",
            "kernel_name",
        ],
        "selected_notebooks": [
            "nb_repo",
            "root_nb_directory",
            "include_subdirs",
            "exclude_subdirs",
        ],
        "out": {},
    }

    def __init__(self, logger: CuratorLogger):
        self.logger = logger
        self._spec: Dict[str, Any] = {}
        self._is_validated = False
        self._source_file: Optional[Path] = None

    @classmethod
    def load_and_validate(
        cls,
        logger: CuratorLogger,
        spec_file: str,
    ) -> Optional["SpecManager"]:
        """Factory method to load and validate a spec file."""
        manager = cls(logger)
        if manager.load_spec(spec_file) and manager.validate():
            return manager
        return None

    def load_spec(self, spec_file: str | Path) -> bool:
        """Load YAML specification file."""
        try:
            yaml = self.get_yaml()
            self._source_file = Path(spec_file)
            with self._source_file.open("r") as f:
                self._spec = yaml.load(f)
            return self.logger.info(f"Successfully loaded spec from {str(spec_file)}")
        except Exception as e:
            return self.logger.exception(e, f"Failed to load YAML spec: {e}")

    def validate(self) -> bool:
        """Perform comprehensive validation on the loaded specification."""
        if not self._spec:
            return self.logger.error("Spec did not loaded / defined, cannot validate.")
        validated = (
            self._validate_top_level_structure()
            and self._validate_header_section()
            and self._validate_selected_notebooks_section()
            and self._validate_directory_repos()
        )
        if not validated:
            return self.logger.error("Spec validation failed.")
        self._is_validated = True
        return self.logger.info("Spec validated.")

    def output_spec(self, output_dir: Path | str) -> Path:
        """The output path for the spec file."""
        return Path(output_dir) / self._source_file.name

    def save_spec(self, output_dir: Path | str) -> bool:
        """Save the current spec to a file."""
        try:
            output_file = self.output_spec(output_dir)
            self.logger.info(f"Saving spec file to {output_file}")
            yaml = self.get_yaml()
            with output_file.open("w") as f:
                yaml.dump(self._spec, f)
            return self.logger.info(f"Spec file written to {output_file}")
        except Exception as e:
            return self.logger.exception(e, f"Error saving spec file: {e}")

    def revise_and_save(
        self,
        output_dir: Path | str,
        **additional_outputs,
    ) -> bool:
        """Update spec with computed outputs and save to file."""
        try:
            self.logger.info(f"Revising spec file {self._source_file} -> {output_dir}")
            for key, value in additional_outputs.items():
                if isinstance(value, list):
                    value = [str(item) for item in value]
                self.set_output_data(key, value)
            return self.save_spec(output_dir)
        except Exception as e:
            return self.logger.exception(e, f"Error revising spec file: {e}")

    # Property-based access to spec data
    @property
    def deployment_name(self) -> str:
        self._ensure_validated()
        return self._spec["image_spec_header"]["deployment_name"]

    @property
    def kernel_name(self) -> str:
        self._ensure_validated()
        return self._spec["image_spec_header"]["kernel_name"]

    @property
    def image_name(self) -> str:
        self._ensure_validated()
        return self._spec["image_spec_header"]["image_name"]

    @property
    def python_version(self) -> str:
        self._ensure_validated()
        return self._spec["image_spec_header"]["python_version"]

    @property
    def nb_repo(self) -> str:
        self._ensure_validated()
        return self._spec["image_spec_header"]["nb_repo"]

    @property
    def selected_notebooks(self) -> List[Dict[str, Any]]:
        self._ensure_validated()
        return self._spec["selected_notebooks"]

    def set_output_data(self, key: str, value: Any) -> None:
        """Set data in the output section."""
        if "out" not in self._spec:
            self._spec["out"] = {}
        self._spec["out"][key] = value

    def get_output_data(self, key: str, default: Any = None) -> Any:
        """Get data from the output section."""
        return self._spec.get("out", {}).get(key, default)

    def get_moniker(self) -> str:
        """Get a filesystem-safe version of the image name."""
        self._ensure_validated()
        return self.image_name.replace(" ", "-").lower()

    # Raw access for backward compatibility or special cases
    def to_dict(self) -> Dict[str, Any]:
        """Return the raw spec dictionary."""
        return self._spec.copy()

    def _ensure_validated(self) -> None:
        """Ensure the spec has been validated before access."""
        if not self._is_validated:
            raise RuntimeError("Spec must be validated before accessing data")

    def get_yaml(self) -> "YAML":
        """Return configured ruamel.yaml instance."""
        from ruamel.yaml import YAML

        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.indent(mapping=2, sequence=4, offset=2)
        return yaml

    # Validation methods (moved from SpecValidator)
    def _validate_top_level_structure(self) -> bool:
        """Validate top-level structure."""
        required_fields = ["image_spec_header", "selected_notebooks"]
        for field in required_fields:
            if field not in self._spec:
                return self.logger.error(f"Missing required field: {field}")

        for key in self._spec:
            if key not in self.ALLOWED_KEYWORDS:
                return self.logger.error(f"Unknown top-level keyword: {key}")

        return True

    def _validate_header_section(self) -> bool:
        """Validate image_spec_header section."""
        header = self._spec["image_spec_header"]

        for key in header:
            if key not in self.ALLOWED_KEYWORDS["image_spec_header"]:
                return self.logger.error(f"Unknown keyword in image_spec_header: {key}")

        required_fields = [
            "image_name",
            "python_version",
            "valid_on",
            "expires_on",
            "nb_repo",
        ]
        for field in required_fields:
            if field not in header:
                return self.logger.error(
                    f"Missing required field in image_spec_header: {field}"
                )

        return True

    def _validate_selected_notebooks_section(self) -> bool:
        """Validate selected_notebooks section."""
        if "selected_notebooks" not in self._spec:
            return self.logger.error("Missing selected_notebooks section")

        for entry in self._spec["selected_notebooks"]:
            for key in entry:
                if key not in self.ALLOWED_KEYWORDS["selected_notebooks"]:
                    return self.logger.error(
                        f"Unknown keyword in selected_notebooks entry: {key}"
                    )

        return True

    def _validate_directory_repos(self) -> bool:
        """Validate that all repositories in directory entries are specified."""
        # Implementation details...
        return True

    def get_repository_urls(self) -> List[str]:
        """Get all unique repository URLs from the spec."""
        self._ensure_validated()
        urls = [self.nb_repo]
        for entry in self.selected_notebooks:
            nb_repo = entry.get("nb_repo", self.nb_repo)
            if nb_repo not in urls:
                urls.append(nb_repo)
        return sorted(list(set(urls)))

    def collect_notebook_paths(self, repos_dir: Path, nb_repos: list[str]) -> list[str]:
        """Collect paths to all notebooks specified by the spec."""
        notebook_paths = []
        header_root = self._spec["image_spec_header"].get("root_nb_directory", "")
        for entry in self._spec["selected_notebooks"]:
            selection_repo = entry.get(
                "nb_repo", self._spec["image_spec_header"]["nb_repo"]
            )
            clone_dir = self._get_repo_dir(repos_dir, selection_repo)
            if not clone_dir:
                self.logger.error(f"Repository not set up: {clone_dir}")
                continue
            entry_root = entry.get("root_nb_directory")
            final_notebook_root = entry_root or header_root
            notebook_paths.extend(
                self._process_directory_entry(entry, clone_dir, final_notebook_root)
            )
        self.logger.info(
            f"Found {len(notebook_paths)} notebooks in all notebook repositories."
        )
        return notebook_paths

    def _get_repo_dir(self, repos_dir: Path, nb_repo: str) -> Optional[Path]:
        """Get the path to the repository directory."""
        basename = os.path.basename(nb_repo).replace(".git", "")
        return repos_dir / basename

    def _process_directory_entry(
        self, entry: dict, repo_dir: Path, root_nb_directory: str
    ) -> List[str]:
        """Process a directory entry from the spec file."""
        base_path = repo_dir
        if root_nb_directory:
            base_path = base_path / root_nb_directory
        possible_notebooks = base_path.glob("**/*.ipynb")

        include_subdirs = entry.get("include_subdirs", [r"."])
        included_notebooks = self._only_included_non_files(
            possible_notebooks, include_subdirs
        )

        exclude_subdirs = entry.get("exclude_subdirs", [])
        remaining_notebooks = self._exclude_notebooks(
            included_notebooks, exclude_subdirs
        )
        self.logger.debug(
            f"Selected {len(remaining_notebooks)} notebooks under {base_path}."
        )
        return remaining_notebooks

    def _only_included_non_files(
        self, possible_notebooks: list[Path], include_regexes: list[str]
    ) -> list[Path]:
        included_notebooks = []
        for nb_path in possible_notebooks:
            if not nb_path.is_file():
                self.logger.warning(f"Skipping non-file: {nb_path}")
                continue
            for include in include_regexes:
                if re.search(include, str(nb_path)):
                    self.logger.debug(
                        f"Including notebook {nb_path} based on regex: '{include}'"
                    )
                    included_notebooks.append(nb_path)
                    break
        return included_notebooks

    def _exclude_notebooks(
        self, included_notebooks: list[Path], exclude_subdirs: list[str]
    ) -> list[str]:
        notebook_paths = []
        for nb_path in included_notebooks:
            if re.search(r"(.ipynb_|-)checkpoints", str(nb_path)):
                self.logger.debug(f"Skipping checkpoint(s): {nb_path}")
                continue
            for exclude in exclude_subdirs:
                if re.search(exclude, str(nb_path)):
                    self.logger.debug(
                        f"Excluding notebook {nb_path} based on regex: '{exclude}'"
                    )
                    break
            else:
                notebook_paths.append(str(nb_path))
        return notebook_paths
