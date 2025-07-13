"""Command line interface for nb-curator."""

import argparse
import sys

from .config import CuratorConfig
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
        "--micromamba-path",
        type=str,
        default=sys.executable,
        help="Path to micromamba program to use for curator and target environments.",
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
        "--clone-repos",
        action="store_true",
        help="Clone any missing notebook repos at --repos-dir. No updates. See also --delete-repos.",
    )
    parser.add_argument(
        "--init-env",
        default=None,
        const="base",
        nargs="?",
        help="Initialize the target environment before curation run. See also --delete-env.",
    )
    parser.add_argument(
        "--curate",
        action="store_true",
        help="Sets options for an 'already initialized' core nb-curator workflow: --compile --install --test-notebooks",
    )
    parser.add_argument(
        "-c",
        "--compile",
        action="store_true",
        help="Compile input package lists to generate pinned requirements",
    )
    parser.add_argument(
        "--no-simplify-paths",
        action="store_true",
        help="Use full input paths in compiler requirements table output",
    )
    parser.add_argument(
        "-i",
        "--install",
        action="store_true",
        help="Install resolved notebook dependencies in system Python environment",
    )
    parser.add_argument(
        "-t",
        "--test-notebooks",
        default=None,
        const=".*",
        nargs="?",
        type=str,
        help="Test notebooks matching patterns (comma-separated regexes)",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        default=1,
        type=int,
        help="Number of parallel jobs for notebook testing",
    )
    parser.add_argument(
        "--timeout",
        default=30 * 60,
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
        help="Submit the injected curation results to the Science Platform Images GitHub repo triggering a build.",
    )
    parser.add_argument(
        "--delete-repos",
        action="store_true",
        help="Delete repo clones after processing",
    )
    parser.add_argument(
        "--delete-target-environment",
        default=None,
        const="base",
        nargs="?",
        help="Delete the target environment after curation run.",
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
    return parser.parse_args()


def main():
    """Main entry point for the CLI."""
    args = parse_args()

    # Create configuration
    config = CuratorConfig(
        spec_file=args.spec_file,
        micromamba_path=args.micromamba_path,
        output_dir=args.output_dir,
        verbose=args.verbose,
        debug=args.debug,
        repos_dir=args.repos_dir,
        clone_repos=args.clone_repos,
        delete_repos=args.delete_repos,
        init_target_environment=args.init_target_environment,
        delete_target_environment=args.delete_target_environment,
        compile=args.compile,
        no_simplify_paths=args.no_simplify_paths,
        install=args.install,
        test_notebooks=args.test_notebooks,
        jobs=args.jobs,
        timeout=args.timeout,
        inject_spi=args.inject_spi,
    )

    # Create and run curator
    curator = NotebookCurator(config)
    success = curator.main()
    curator.print_log_counters()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
