"""Discover every package suite and fail when no tests are found."""

import argparse
from pathlib import Path
import sys
import unittest


SUITES = {"infra": "tests", "db": "db_lib/tests", "cli": "tools_cli/tests"}


def run_tests(root, selected="all", stream=None):
    stream = stream or sys.stderr
    suite = unittest.TestSuite()
    names = SUITES if selected == "all" else [selected]
    for name in names:
        directory = root / SUITES[name]
        if not directory.is_dir():
            print(f"{name}: no test directory in this revision", file=stream)
            continue
        discovered = unittest.TestLoader().discover(str(directory), pattern="test_*.py")
        print(f"{name}: {discovered.countTestCases()} tests", file=stream)
        suite.addTests(discovered)
    if not suite.countTestCases():
        print("No tests discovered; refusing to report success.", file=stream)
        return 2
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["all", *SUITES], default="all")
    args = parser.parse_args(argv)
    return run_tests(Path(__file__).resolve().parents[1], args.suite)


if __name__ == "__main__":
    raise SystemExit(main())
