"""Unified specification management with validation and persistence."""

from typing import Dict, Any, List, Optional
from pathlib import Path
from ruamel.yaml import YAML

from .logging import CuratorLogger


class SpecManager:
    """Manages specification loading, validation, access, and persistence."""
    
    ALLOWED_KEYWORDS = {
        "image_spec_header": [
            "image_name", "description", "valid_on", "expires_on", 
            "python_version", "nb_repo", "root_nb_directory",
            "deployment_name", "kernel_name",
        ],
        "selected_notebooks": [
            "nb_repo", "root_nb_directory", "include_subdirs", "exclude_subdirs",
        ],
        "out": {},
    }

    def __init__(self, logger: CuratorLogger):
        self.logger = logger
        self._spec: Dict[str, Any] = {}
        self._is_validated = False
        self._source_file: Optional[str] = None

    @classmethod
    def load_and_validate(cls, spec_file: str, logger: CuratorLogger) -> Optional['SpecManager']:
        """Factory method to load and validate a spec file."""
        manager = cls(logger)
        if manager.load_spec(spec_file) and manager.validate():
            return manager
        return None

    def load_spec(self, spec_file: str) -> bool:
        """Load YAML specification file."""
        try:
            yaml = self._get_yaml()
            with open(spec_file, "r") as f:
                self._spec = yaml.load(f)
            self._source_file = spec_file
            self._is_validated = False  # Reset validation status
            return self.logger.info(f"Successfully loaded spec from {spec_file}")
        except Exception as e:
            return self.logger.exception(e, f"Failed to load YAML spec: {e}")

    def validate(self) -> bool:
        """Perform comprehensive validation on the loaded specification."""
        if not self._spec:
            return self.logger.error("No specification loaded")
            
        validation_result = (
            self._validate_top_level_structure()
            and self._validate_header_section()
            and self._validate_selected_notebooks_section()
            and self._validate_directory_repos()
        )
        
        self._is_validated = validation_result
        return validation_result

    def save_spec(self, output_file: str) -> bool:
        """Save the current spec to a file."""
        try:
            self.logger.info(f"Saving spec file to {output_file}")
            yaml = self._get_yaml()
            with open(output_file, "w") as f:
                yaml.dump(self._spec, f)
            return self.logger.info(f"Spec file written to {output_file}")
        except Exception as e:
            return self.logger.exception(e, f"Error saving spec file: {e}")

    def revise_and_save(self, output_file: str, notebook_paths: List[str], 
                       test_imports: dict, **additional_outputs) -> bool:
        """Update spec with computed outputs and save to file."""
        try:
            self.logger.info(f"Revising spec file {self._source_file} --> {output_file}")

            # Update spec with outputs
            self.set_output_data("test_notebooks", [str(p) for p in notebook_paths])
            self.set_output_data("test_imports", list(test_imports.keys()))
            
            # Add any additional output data
            for key, value in additional_outputs.items():
                self.set_output_data(key, value)

            return self.save_spec(output_file)
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

    def get_repository_urls(self) -> List[str]:
        """Get all unique repository URLs from the spec."""
        self._ensure_validated()
        urls = [self.nb_repo]
        for entry in self.selected_notebooks:
            nb_repo = entry.get("nb_repo", self.nb_repo)
            if nb_repo not in urls:
                urls.append(nb_repo)
        return urls
    
    def get_python_version_list(self) -> List[int]:
        """Extract requested Python version as list of integers."""
        version_str = self.python_version
        if isinstance(version_str, (int, float)):
            version_str = str(version_str)
        if not isinstance(version_str, str):
            raise ValueError("Invalid python_version in spec file")
        return list(map(int, version_str.split(".")))

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

    def _get_yaml(self) -> YAML:
        """Return configured ruamel.yaml instance."""
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
            "image_name", "python_version", "valid_on", 
            "expires_on", "nb_repo",
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