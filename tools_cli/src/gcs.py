import pathlib

import click
from git import Repo, exc


TREES_PATH = pathlib.Path("~/.config/tools/gcs/trees/").resolve()


def is_git_repo(path):
    try:
        _ = Repo(path).git_dir
        return True
    except exc.InvalidGitRepositoryError:
        return False


@click.command(help="Create worktree changeset")
@click.option('--branch-name', help='Name of branch.')
def main(branch_name):
    TREES_PATH.mkdir(parents=True, exist_ok=True)

    repo_path = pathlib.Path(".").resolve()
    if not is_git_repo(repo_path):
        raise RuntimeError("not in a git repo")
    repo = Repo(repo_path)

    tree_name = f"{repo_path.name}|{branch_name}"
    tree_path = TREES_PATH / tree_name
    if tree_path.exists():
        raise RuntimeError("worktree already exists")

    repo.git.worktree(
        "add",
        tree_path,
        branch_name,
    )

    print(tree_path)


if __name__ == "__main__":
    main()
