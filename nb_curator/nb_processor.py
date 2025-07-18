"""Notebook processing for import extraction and path collection."""

import json
import re
from pathlib import Path
from typing import Dict, List, Set, Optional

from .logging import CuratorLogger


class NotebookImportProcessor:
    """Processes notebooks to extract imports."""

    def __init__(self, logger: CuratorLogger):
        self.logger = logger
        self.import_pattern = re.compile(
            r"^(?:import\s+([a-zA-Z0-9_\.]+))|(?:from\s+([a-zA-Z0-9_\.]+)\s+import)"
        )

    def extract_imports(self, notebook_paths: List[str]) -> Dict[str, List[str]]:
        """Extract import statements from notebooks."""
        import_to_nb: Dict[str, List[str]] = {}
        unique_notebooks = set(notebook_paths)
        self.logger.info(
            f"Processing {len(unique_notebooks)} unique notebooks for imports."
        )
        for nb_path_str in unique_notebooks:
            nb_dict = self._read_notebook_json(nb_path_str)
            if nb_dict:
                imports = self._extract_imports_from_notebook(nb_dict)
                for imp in imports:
                    if imp not in import_to_nb:
                        import_to_nb[imp] = []
                    import_to_nb[imp].append(nb_path_str)
                self.logger.debug(f"Extracted {len(imports)} package imports from notebook {nb_path_str}: \n{sorted(list(imports))}")
        self.logger.info(f"Extracted {len(import_to_nb)} package imports from {len(unique_notebooks)} notebooks.")
        return sorted(list(import_to_nb.keys()))

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
