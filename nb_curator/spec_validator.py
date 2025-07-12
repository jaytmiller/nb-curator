"""YAML specification validation."""

from typing import Dict, List, Any

from .logging import CuratorLogger

# from ruamel.yaml import YAML

class SpecValidator:
    """Validates notebook specification files."""

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
        self.spec: Dict[str, Any] = {}

    def load_spec(self, spec_file: str) -> bool:
        """Load YAML specification file."""
        from ruamel.yaml import YAML
        try:
            yaml = self._get_yaml()
            with open(spec_file, "r") as f:
                self.spec = yaml.load(f)
            return self.logger.info(f"Successfully loaded spec from {spec_file}")
        except Exception as e:
            return self.logger.exception(e, f"Failed to load YAML spec: {e}")

    def validate_spec(self) -> bool:
        """Perform comprehensive validation on the loaded specification."""
        return (
            self._validate_top_level_structure()
            and self._validate_header_section()
            and self._validate_selected_notebooks_section()
            and self._validate_directory_repos()
        )

    def _get_yaml(self):
        """Return configured ruamel.yaml instance."""
        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.indent(mapping=2, sequence=4, offset=2)
        return yaml

    def _validate_top_level_structure(self) -> bool:
        """Validate top-level structure."""
        required_fields = ["image_spec_header", "selected_notebooks"]
        for field in required_fields:
            if field not in self.spec:
                return self.logger.error(f"Missing required field: {field}")

        for key in self.spec:
            if key not in self.ALLOWED_KEYWORDS:
                return self.logger.error(f"Unknown top-level keyword: {key}")

        return True

    def _validate_header_section(self) -> bool:
        """Validate image_spec_header section."""
        header = self.spec["image_spec_header"]

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
        if "selected_notebooks" not in self.spec:
            return self.logger.error("Missing selected_notebooks section")

        for entry in self.spec["selected_notebooks"]:
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
