import json
import pathlib

from git import Repo, exc

from rich.live import Live
from rich.prompt import Prompt, Confirm
from rich.style import Style
from rich.table import Table
from rich.syntax import Syntax

from readchar import readkey, key

from _env import REPOS_PATH
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
    repo.git.stash("store", "-m", name, commit)
    repo.git.stash()


def apply_stash(repo: Repo, stash_index: str):
    repo.git.stash("pop", f"stash@{{{stash_index}}}")


def get_stashes(repo_paths: list[str]):
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


def main():
    current_path = pathlib.Path(".").resolve()
    try:
        current_repo_path = get_project_from_path(current_path)
    except:
        current_repo_path = None

    if current_repo_path:
        repo_paths = [current_repo_path]
    else:
        repo_paths = list(REPOS_PATH.iterdir())

    selected = 0
    items = get_stashes(repo_paths)

    try:
        with Live(print_table(make_table(), items, selected), auto_refresh=False) as live:
            while True:
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
                        save_stash_name()

                        live.start()
                    case "a":
                        confirmed = Confirm.ask("apply stash?", default=False, console=live.console)
                        if confirmed:
                            apply_stash(stash_data["repo"], stash_data["stash_index"])

                        items = get_stashes(repo_paths)

                live.update(print_table(make_table(), items, selected), refresh=True)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
