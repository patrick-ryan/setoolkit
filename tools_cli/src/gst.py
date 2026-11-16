import json
import pathlib

import click
from git import Repo, exc

from rich.live import Live
from rich.prompt import Prompt, Confirm
from rich.style import Style
from rich.table import Table
from rich.syntax import Syntax

from readchar import readkey, key

from _env import get_repos_path
from rt import get_project_from_path


SELECTED = Style(color="blue", bgcolor="white", bold=True)


def is_git_repo(path):
    try:
        _ = Repo(path).git_dir
        return True
    except exc.InvalidGitRepositoryError:
        return False


def make_table():
    table = Table(title="Stashes")

    table.add_column("Repo", style="magenta")
    table.add_column("Date", justify="right", style="cyan", no_wrap=True)
    table.add_column("Message", justify="left", style="green")

    return table


def print_table(table, rows, selected=0):
    for i, row in enumerate(rows):
        row_vals = [row[k] for k in row["row"]]
        if i == selected:
            table.add_row(*row_vals, style=SELECTED)
        else:
            table.add_row(*row_vals)

    return table


def print_diff(stash_data):
    return Syntax(stash_data["repo"].git.stash("show", "-p", stash_data["commit"]), "diff")


def save_stash_name(repo: Repo, commit: str, name: str):
    entries = repo.git.stash("list", "--format=%H%x00%gs").splitlines()
    for index, entry in enumerate(entries):
        sha, message = entry.split("\0", 1)
        if sha == commit:
            break
    else:
        raise click.ClickException("The selected stash no longer exists.")
    if message == name:
        return

    # Store a new commit with identical contents before removing the old entry.
    # A distinct commit also allows renaming the top stash without reflog deduplication.
    original = repo.commit(commit)
    parents = [arg for parent in original.parents for arg in ("-p", parent.hexsha)]
    renamed = repo.git.commit_tree(original.tree.hexsha, *parents, "-m", name)
    repo.git.stash("store", "-m", name, renamed)
    updated = repo.git.stash("list", "--format=%H").splitlines()
    if len(updated) != len(entries) + 1 or updated[0] != renamed or updated[index + 1] != commit:
        raise click.ClickException("Could not store the renamed stash; the original was retained.")
    repo.git.stash("drop", f"stash@{{{index + 1}}}")


def apply_stash(repo: Repo, stash_index: int, expected_commit: str | None = None):
    if expected_commit is not None and repo.commit(f"stash@{{{stash_index}}}").hexsha != expected_commit:
        raise click.ClickException("The stash list changed; refresh before applying the selected stash.")
    repo.git.stash("pop", f"stash@{{{stash_index}}}")


def get_stashes(repo_paths: list[pathlib.Path]):
    stashes = {}
    for repo_path in repo_paths:
        if is_git_repo(repo_path):
            repo = Repo(repo_path)
            stash_lines: str = repo.git.stash(
                "list",
                "--date=short",
                """--pretty=format:{%n  "commit": "%H",%n  "date": "%ad",%n  "message": "%f"%n},""",
            )
            stash_json = f"[ {stash_lines.strip(', ')} ]"
            stashes[repo_path.name] = {
                s["commit"]:
                {
                    "repo": repo,
                    "repo_name": repo_path.name,
                    "date": s["date"],
                    "message": s["message"],
                    "commit": s["commit"],
                    "stash_index": i,
                    "row": ["repo_name", "date", "message"],
                }
                for i, s in enumerate(json.loads(stash_json))
            }
    return [s for _, rstashes in stashes.items() for s in rstashes.values()]


@click.command()
def main():
    current_path = pathlib.Path(".").resolve()
    try:
        current_repo_path = get_project_from_path(current_path)
    except ValueError:
        current_repo_path = None

    if current_repo_path:
        repo_paths = [current_repo_path]
    else:
        repo_paths = list(get_repos_path().iterdir())

    selected = 0
    items = get_stashes(repo_paths)
    if not items:
        print("No stashes")
        return

    try:
        with Live(print_table(make_table(), items, selected), auto_refresh=False) as live:
            while items:
                stash_data = items[selected]
                match readkey():
                    case key.UP | "k":
                        selected = max(0, selected - 1)
                    case key.DOWN  | "j":
                        selected = min(len(items) - 1, selected + 1)
                    case key.ENTER:
                        # prevents an extra line from printing on stop
                        live._alt_screen = True

                        live.stop()
                        live._alt_screen = False

                        with live.console.pager(styles=True):
                            live.console.print(print_diff(stash_data))

                        live.start()
                    case "r":
                        # prevents an extra line from printing on stop
                        live._alt_screen = True

                        live.stop()
                        live._alt_screen = False

                        live.console.clear()

                        name = Prompt.ask("Stash name:", default=stash_data["message"], console=live.console)
                        save_stash_name(stash_data["repo"], stash_data["commit"], name)
                        items = get_stashes(repo_paths)

                        live.start()
                    case "a":
                        confirmed = Confirm.ask("apply stash?", default=False, console=live.console)
                        if confirmed:
                            apply_stash(stash_data["repo"], stash_data["stash_index"], stash_data["commit"])

                        items = get_stashes(repo_paths)

                selected = min(selected, max(0, len(items) - 1))
                live.update(print_table(make_table(), items, selected), refresh=True)
    except KeyboardInterrupt:
        pass
    except exc.GitCommandError as error:
        raise click.ClickException(str(error)) from error


if __name__ == "__main__":
    main()
