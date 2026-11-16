import pathlib

import click
from git import Repo, exc


TREES_PATH = pathlib.Path("~/.config/tools/gcs/trees/").expanduser().resolve()


@click.command(help="Create worktree changeset")
@click.option('--branch-name', required=True, help='Existing branch to check out.')
def main(branch_name):
    try:
        repo = Repo(pathlib.Path.cwd(), search_parent_directories=True)
    except (exc.InvalidGitRepositoryError, exc.NoSuchPathError) as error:
        raise click.ClickException("Not in a git repository") from error
    repo_path = pathlib.Path(repo.working_tree_dir)

    tree_name = f"{repo_path.name}|{branch_name}"
    tree_path = TREES_PATH / tree_name
    if tree_path.exists():
        raise click.ClickException("Worktree already exists")

    TREES_PATH.mkdir(parents=True, exist_ok=True)
    try:
        repo.git.worktree("add", tree_path, branch_name)
    except exc.GitCommandError as error:
        raise click.ClickException(str(error)) from error

    print(tree_path)


if __name__ == "__main__":
    main()
