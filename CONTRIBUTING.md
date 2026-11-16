# Contributing

## Development setup

Use Python 3.11 or 3.12 for the shared development environment:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

`requirements-dev.txt` defines the combined test environment. Keep its runtime
constraints aligned with both packages' metadata when changing dependencies.
The packages can also be installed separately; their own `pyproject.toml` files
define supported Python versions. The database package's lower Python floor
should receive an install/import smoke test when its metadata changes.

## Unit and regression tests

From any working directory, invoke the script by its path:

```sh
python scripts/run_tests.py
python scripts/run_tests.py --suite db
python scripts/run_tests.py --suite cli
python scripts/run_tests.py --suite infra
```

The runner discovers `tests/`, `db_lib/tests/`, and `tools_cli/tests/` independently,
so test directories do not need package `__init__.py` files. It reports each
suite's count, returns nonzero on failures/import errors, and rejects a run with
no tests. During adoption, missing suite directories are reported explicitly.

Keep regressions with their fixes. Prefer observable behavior: existing table
contents survive failed imports; canceled navigation retains the working
directory; stash operations preserve staged, unstaged, and untracked changes;
review responses are classified correctly. Use temporary Git repositories and
mock AWS/GitHub reads rather than requiring credentials in CI.

GitHub Actions runs on Ubuntu and macOS with Python 3.11 and 3.12. It checks dependency
compatibility, Python correctness lint, shell syntax, and all discovered tests.
Fork PR runs may need the upstream maintainer's first-contributor approval.

## Style

- Use four spaces, double-quoted strings, and a 100-character formatting target.
- Keep imports grouped as standard library, third-party, then local modules.
- Give public helpers accurate parameter/return annotations. Use specific
  exceptions and actionable Click errors at CLI boundaries.
- Keep input/output and terminal rendering separate from reusable logic.
- Use `pathlib` for filesystem paths and quote shell expansions.
- Preserve meaningful comments such as DuckDB replacement-scan references;
  SQL references to a local `df` are not ordinary unused variables.

```sh
python -m ruff check .
python -m ruff format --check path/to/changed_file.py
```

The initial lint gate catches syntax errors, undefined names, and invalid control
flow. Formatting and broader import/unused-variable rules are not yet CI gates;
apply formatting to touched code without mixing whole-project reformatting into
behavioral fixes. The checked-in `ruff.toml` makes the rules reproducible.

## Pull requests

Use one concern per PR and include its regression tests, exact validation command,
and integration limitations. Push to your fork and explicitly select upstream
`main` as the base. Add related follow-up commits to the existing PR rather than
opening duplicate fixes. Link genuine dependencies and record the merge order.

Use GitHub CLI for independent fork PRs. Native `gh stack` is appropriate when
changes are truly dependent and the repository supports stacked PRs. Test combined
changes in a disposable worktree; preserve the contributor's current checkout.

Do not delete ignored build output merely because it exists. Preview cleanup with
`git clean -ndX` and remove only artifacts you own or have been asked to remove.
