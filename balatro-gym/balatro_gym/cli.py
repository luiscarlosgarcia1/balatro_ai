"""Command-line interface for running Balatro Gym workflows."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from contextlib import redirect_stderr
from typing import TextIO

from .watchable_session import run_watchable_session


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the ``balatro-gym`` command and return its process exit code."""
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = _build_parser()
    with redirect_stderr(stderr):
        arguments = parser.parse_args(argv)

    if arguments.command == "watch":
        result = run_watchable_session(
            arguments.seed,
            keep_open=arguments.keep_open,
            output=stdout,
            diagnostics=stderr,
        )
        return result.exit_code

    parser.error(f"Unknown command: {arguments.command}")
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="balatro-gym")
    commands = parser.add_subparsers(dest="command", required=True)
    watch = commands.add_parser("watch", help="run one visible seeded session")
    watch.add_argument("--seed", required=True, help="seed for the Red Deck / White Stake run")
    watch.add_argument(
        "--keep-open",
        action="store_true",
        help="keep the Balatro window open after the blind settles",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
