"""Notebook processing for import extraction and path collection."""

import json
import re
from pathlib import Path
from typing import Dict, List, Set, Optional

from .logging import CuratorLogger


class NotebookProcessor:
    """Processes notebooks to extract imports and collect paths."""

    def __init__(self, logger: CuratorLogger):
        self.logger = logger
        self.import_pattern = re.compile(
            r"^(?:import\s+([a-zA-Z0-9_\.]+))|(?:from\s+([a-zA-Z0-9_\.]+)\s+import)"
        )

    def collect_notebook_paths(self, spec: dict, repos_to_setup: dict) -> List[str]:
        """Collect paths to all notebooks specified in the spec."""
        notebook_paths = []

        for entry in spec["selected_notebooks"]:
            nb_repo = entry.get("nb_repo", spec["image_spec_header"]["nb_repo"])
            repo_dir = repos_to_setup[nb_repo]

            if not repo_dir:
                self.logger.error(f"Repository not set up: {nb_repo}")
                continue

            root_nb_directory = entry.get(
                "root_nb_directory",
                spec["image_spec_header"].get("root_nb_directory", ""),
            )

            notebook_paths.extend(
                self._process_directory_entry(entry, repo_dir, root_nb_directory)
            )

        self.logger.info(f"Found {len(notebook_paths)} notebooks")
        return notebook_paths

    def extract_imports(self, notebook_paths: List[str]) -> Dict[str, List[str]]:
        """Extract import statements from notebooks."""
        import_to_nb: Dict[str, List[str]] = {}
        unique_notebooks = set(notebook_paths)

        self.logger.info(
            f"Processing {len(unique_notebooks)} unique notebooks for imports"
        )

        for nb_path_str in unique_notebooks:
            nb_dict = self._read_notebook_json(nb_path_str)
            if nb_dict:
                imports = self._extract_imports_from_notebook(nb_dict)
                for imp in imports:
                    if imp not in import_to_nb:
                        import_to_nb[imp] = []
                    import_to_nb[imp].append(nb_path_str)

        self.logger.info(f"Extracted {len(import_to_nb)} imports")
        return import_to_nb

    def _process_directory_entry(
        self, entry: dict, repo_dir: Path, root_nb_directory: str
    ) -> List[str]:
        """Process a directory entry from the spec file."""
        base_path = repo_dir
        if root_nb_directory:
            base_path = base_path / root_nb_directory

        notebook_paths = []
        include_subdirs = entry.get("include_subdirs", ["."])
        exclude_subdirs = entry.get("exclude_subdirs", [])

        for subdir in include_subdirs:
            subdir_path = base_path / subdir
            if not subdir_path.exists():
                self.logger.warning(f"Included directory does not exist: {subdir_path}")
                continue

            for nb_path in subdir_path.glob("**/*.ipynb"):
                if not any(exclude in str(nb_path) for exclude in exclude_subdirs):
                    notebook_paths.append(str(nb_path))

        return notebook_paths

    def _read_notebook_json(self, nb_path: str) -> Optional[dict]:
        """Read and parse a notebook file as JSON."""
        try:
            with open(nb_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            self.logger.warning(f"Could not parse notebook {nb_path} as JSON")
            return None

    def _extract_imports_from_notebook(self, notebook: dict) -> Set[str]:
        """Extract import statements from a notebook."""
        imports = set()

        for cell in notebook.get("cells", []):
            if cell.get("cell_type") == "code":
                source = self._get_cell_source(cell)

                for line in source.split("\n"):
                    line = line.strip()
                    match = self.import_pattern.match(line)
                    if match:
                        root_package = self._extract_root_package(match)
                        if root_package:
                            imports.add(root_package)

        return imports

    def _get_cell_source(self, cell: dict) -> str:
        """Get the source code from a notebook cell."""
        source = cell.get("source", "")
        if isinstance(source, list):
            return "".join(source)
        return source

    def _extract_root_package(self, match) -> Optional[str]:
        """Extract the root package name from a regex match."""
        package_path = match.group(1) or match.group(2)
        if package_path is None:
            return None

        root_package = package_path.split(".")[0]

        # Skip built-in modules
        if root_package in ["__future__", "builtins", "sys", "os"]:
            return None

        return root_package
