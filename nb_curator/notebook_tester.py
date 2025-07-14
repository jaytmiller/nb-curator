"""Notebook testing functionality."""

import datetime
import glob
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from typing import List, Tuple

from .logging import CuratorLogger


NOTEBOOK_MAX_SECS = 30 * 60


class NotebookTester:
    """Tests notebooks by executing them in isolated environments."""

    def __init__(
        self,
        logger: CuratorLogger,
        environment: str = "base",
        jobs: int = 1,
        timeout: int = NOTEBOOK_MAX_SECS,
    ):
        self.logger = logger
        self.environment = environment
        self.jobs = jobs
        self.timeout = timeout

    def filter_notebooks(
        self, notebook_paths: List[str], test_patterns: str
    ) -> List[str]:
        """Filter notebooks based on test patterns."""
        import re

        unique_notebooks = set()
        for nb_path in sorted(notebook_paths):
            for regex in test_patterns.split(","):
                if re.search(regex, nb_path):
                    unique_notebooks.add(nb_path)

        filtered = sorted(unique_notebooks)
        self.logger.info(f"Filtered notebook list to {len(filtered)} entries")
        return filtered

    def test_notebooks(self, notebook_paths: List[str]) -> bool:
        """Test multiple notebooks in parallel."""
        self.logger.info(
            f"Testing {len(notebook_paths)} notebooks with {self.jobs} jobs"
        )

        failing_notebooks = []

        with ProcessPoolExecutor(max_workers=self.jobs) as executor:
            results = executor.map(
                self._test_single_notebook,
                notebook_paths,
                [self.environment] * len(notebook_paths),
                [self.timeout] * len(notebook_paths),
            )

            for failed, notebook, output in results:
                sys.stdout.write(output)
                sys.stdout.flush()
                if failed:
                    failing_notebooks.append(notebook)

        if failing_notebooks:
            self._print_divider("FAILED")
            for notebook in failing_notebooks:
                self.logger.error(f"Notebook {notebook} failed tests")
            return False

        self.logger.info("All notebooks passed tests")
        return True

    def _test_single_notebook(
        self, notebook: str, environment: str, timeout: int
    ) -> Tuple[bool, str, str]:
        """Test a single notebook in isolation."""
        if notebook.startswith("#"):
            return False, notebook, self._print_divider(f"Skipping {notebook}")

        base_nb = os.path.basename(notebook)
        start = datetime.datetime.now()

        output = self._print_divider(
            f"Testing '{base_nb}' on environment '{environment}'"
        )

        here = os.getcwd()
        err = True  # assume failed

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                source_path = os.path.dirname(os.path.abspath(notebook))
                test_dir = os.path.join(temp_dir, "notebook-test")
                shutil.copytree(source_path, test_dir)
                os.chdir(test_dir)

                # Set permissions
                os.chmod(test_dir, stat.S_IRWXU)
                for path in glob.glob("*"):
                    os.chmod(path, stat.S_IRWXU)

                # Run the notebook
                if notebook.endswith(".ipynb"):
                    cmd = [
                        "papermill",
                        "--no-progress-bar",
                        os.path.basename(notebook),
                        "-k",
                        environment,
                        "test.ipynb",
                    ]
                elif notebook.endswith(".py"):
                    cmd = ["python", os.path.basename(notebook)]
                else:
                    raise ValueError(f"Unhandled test file extension: {notebook}")

                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=timeout,
                )

                err = result.returncode != 0
                output += result.stdout

        except Exception as e:
            output += f"Exception during testing: {str(e)}\n"
            err = True
        finally:
            os.chdir(here)

        elapsed = datetime.datetime.now() - start
        status = "OK" if not err else "FAIL"
        output += self._print_divider(f"Tested {base_nb} {status} {elapsed}")

        return err, notebook, output

    def _print_divider(self, title: str, char: str = "*", width: int = 100) -> str:
        """Create a divider string with centered title."""
        return f" {title} ".center(width, char) + "\n"
