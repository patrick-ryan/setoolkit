import pathlib

from typing import Callable

from _env import REPOS_PATH


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


def get_project_from_path(path: pathlib.Path) -> str:
    if REPOS_PATH in path.parents:
        project_dir = find_parent_with_parent(path, REPOS_PATH)
        return project_dir
    else:
        raise Exception("not in projects path")


def main():
    current_dir = pathlib.Path(".").resolve()
    print(str(get_project_from_path(current_dir)))


if __name__ == "__main__":
    main()
