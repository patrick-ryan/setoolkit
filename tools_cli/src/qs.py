import pathlib

import click
from thefuzz import process

from rich.live import Live
from rich.prompt import Prompt, Confirm
from rich.style import Style
from rich.table import Table
from rich.syntax import Syntax

from readchar import readkey, key

from rt import get_project_from_path


SELECTED = Style(color="dark_blue", bgcolor="white", bold=True)


def make_table():
    table = Table(box=None)
    table.add_column(style="magenta")
    return table


def print_table(table, rows, selected=0):
    for i, item in enumerate(rows):
        if i == selected:
            table.add_row(item, style=SELECTED)
        else:
            table.add_row(item)

    return table


@click.command()
@click.argument("text")
def main(text: str):
    """
    Quick search for projects, by project name
    """

    cd = get_project_from_path(pathlib.Path(".").resolve())
    paths = cd.glob("**/autoci.json")

    results = [str(r) for r, _ in process.extract(text, paths, limit=5)]

    try:
        selected = 0
        with Live(print_table(make_table(), results, selected), auto_refresh=False) as live:
            while True:
                match readkey():
                    case key.UP | "k":
                        selected = max(0, selected - 1)
                    case key.DOWN  | "j":
                        selected = min(len(results) - 1, selected + 1)
                    case key.ENTER:
                        pathlib.Path("/tmp/qs").write_text(str(pathlib.Path(results[selected]).parent))
                        break

                live.update(print_table(make_table(), results, selected), refresh=True)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
