import pathlib
import os

import click


def get_repos_path() -> pathlib.Path:
    value = os.getenv("SETOOLKIT_CODE_PATH")
    if not value:
        raise click.ClickException("Set SETOOLKIT_CODE_PATH to your repository directory.")
    path = pathlib.Path(value).expanduser().resolve()
    if not path.is_dir():
        raise click.ClickException(f"Repository directory does not exist: {path}")
    return path
