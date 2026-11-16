import pathlib

from typing import Callable

import click

from _env import get_repos_path


def find_parent(path: pathlib.Path, cond: Callable[[pathlib.Path], bool]) -> pathlib.Path:
    for parent in path.parents:
        if cond(parent):
            return parent
    raise RuntimeError("No parent found")


def find_parent_with_parent(path: pathlib.Path, parent: pathlib.Path) -> pathlib.Path:
    if path.parent == parent:
        return path
    return find_parent(
        path,
        lambda p: p.parent == parent
    )


def get_project_from_path(path: pathlib.Path) -> pathlib.Path:
    repos_path = get_repos_path()
    if repos_path in path.parents:
        project_dir = find_parent_with_parent(path, repos_path)
        return project_dir
    else:
        raise ValueError(f"Not inside a project under {repos_path}")


@click.command()
def main():
    current_dir = pathlib.Path(".").resolve()
    try:
        print(str(get_project_from_path(current_dir)))
    except ValueError as error:
        raise click.ClickException(str(error)) from error


if __name__ == "__main__":
    main()
