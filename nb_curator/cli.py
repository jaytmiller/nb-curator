"""Command line interface for nb-curator."""

import sys
import argparse

from .config import (
    CuratorConfig,
    DEFAULT_MICROMAMBA_PATH,
    NOTEBOOK_TEST_MAX_SECS,
    NOTEBOOK_TEST_JOBS,
)
from .curator import NotebookCurator


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Process notebook image specification YAML and prepare notebook environment and tests."
    )
    parser.add_argument(
        "spec_file", type=str, help="Path to the YAML specification file."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./output",
        help="Directory to store output files",
    )
    parser.add_argument(
        "--repos-dir",
        type=str,
        default="./references",
        help="Directory to store/locate cloned repos; unlike git-sync, these are writable.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable DEBUG log output",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debugging with pdb on exceptions.",
    )
    parser.add_argument(
        "--log-times",
        action="store_true",
        help="Include ISO timestamps in log messages.",
    )
    parser.add_argument(
        "--init-env",
        action="store_true",
        help="Create and kernelize the target environment before curation run. See also --delete-env.",
    )
    parser.add_argument(
        "--delete-env",
        action="store_true",
        help="Completely delete the target environment after processing.",
    )
    parser.add_argument(
        "--curate",
        action="store_true",
        help="Sets options for an 'already initialized' core nb-curator workflow: --compile --install --test-notebooks",
    )
    parser.add_argument(
        "-c",
        "--compile-packages",
        action="store_true",
        help="Compile spec and input package lists to generate pinned requirements and other metadata for target environment.",
    )
    parser.add_argument(
        "-i",
        "--install-packages",
        action="store_true",
        help="Install compiled base and pip requirements into target/test environment.",
    )
    parser.add_argument(
        "--uninstall-packages",
        action="store_true",
        help="Remove the compiled packages from the target environment after processing.",
    )
    parser.add_argument(
        "-t",
        "--test-notebooks",
        default=None,
        const=".*",
        nargs="?",
        type=str,
        help="Test notebooks matching patterns (comma-separated regexes) in target environment.",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        default=NOTEBOOK_TEST_JOBS,
        type=int,
        help="Number of parallel jobs for notebook testing",
    )
    parser.add_argument(
        "--timeout",
        default=NOTEBOOK_TEST_MAX_SECS,
        type=int,
        help="Timeout in seconds for notebook tests",
    )
    parser.add_argument(
        "--inject-spi",
        action="store_true",
        help="Inject curation products into the Science Platform Images repo clone.",
    )
    parser.add_argument(
        "--submit-for-build",
        action="store_true",
        help="Submit the updated spec and curation results to the Science Platform Images GitHub repo triggering a build.",
    )
    parser.add_argument(
        "--delete-repos",
        action="store_true",
        help="Delete --repo-dir and clones after processing.",
    )
    parser.add_argument(
        "--micromamba-path",
        type=str,
        default=DEFAULT_MICROMAMBA_PATH,
        help="Path to micromamba program to use for curator environment management.",
    )
    parser.add_argument(
        "--reset-spec",
        action="store_true",
        help="Reset spec to its original state by deleting output fields.",
    )
    return parser.parse_args()


def main():
    """Main entry point for the CLI."""
    args = parse_args()
    # Create configuration
    config = CuratorConfig(
        spec_file=args.spec_file,
        output_dir=args.output_dir,
        verbose=args.verbose,
        debug=args.debug,
        log_times=args.log_times,
        micromamba_path=args.micromamba_path,
        repos_dir=args.repos_dir,
        delete_repos=args.delete_repos,
        init_env=args.init_env,
        delete_env=args.delete_env,
        compile_packages=args.compile_packages,
        install_packages=args.install_packages,
        uninstall_packages=args.uninstall_packages,
        test_notebooks=args.test_notebooks,
        jobs=args.jobs,
        timeout=args.timeout,
        reset_spec=args.reset_spec,
        inject_spi=args.inject_spi,
        submit_for_build=args.submit_for_build,
        curate=args.curate,
    )

    # Create and run curator
    curator = NotebookCurator(config)
    success = curator.main()
    curator.print_log_counters()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
