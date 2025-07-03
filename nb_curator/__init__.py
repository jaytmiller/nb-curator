"""
nb-curator: A notebook curation tool for managing Jupyter notebook environments.
"""

__version__ = "0.1.0"

from .curator import NotebookCurator
from .config import CuratorConfig

__all__ = ["NotebookCurator", "CuratorConfig"]
