import dataclasses
import datetime
import functools
import itertools
import os
import re
from typing import Literal
import webbrowser

import click
from dateutil import parser
from github import Github, Auth, Consts, Repository, PullRequest
from readchar import readkey, key
from rich.live import Live
from rich.markup import escape
from rich.style import Style
from rich.table import Table


SELECTED = Style(color="blue", bgcolor="white", bold=True)


@dataclasses.dataclass
class TableRow():
    repo_id: int
    pr_id: int
    url: str
    pr: str
    repo: str
    date: str
    state: Literal["MENTIONED", "UNRESPONDED", "MINE"]
    comment: str | None
    row: list[str]

    def __eq__(self, other):
        if not isinstance(other, TableRow):
            return NotImplemented
        return self.repo_id == other.repo_id and self.pr_id == other.pr_id

    def __hash__(self):
        return hash((self.repo_id, self.pr_id))

    @staticmethod
    def from_dict(d: dict):
        self = TableRow(**d)
        return self


def get_open_pulls(repos: list[Repository.Repository]):

    for repo in repos:
        for pull in repo.get_pulls():
            if not pull.closed_at and not pull.merged:
                yield (repo, pull)


@functools.cache
def get_comments(pull: PullRequest.PullRequest):
    return list(itertools.chain(
        pull.get_review_comments(),
        pull.get_issue_comments(),
    ))


def is_recent(created_at, since):
    if since is None:
        return True
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=datetime.timezone.utc)
    if since.tzinfo is None:
        since = since.replace(tzinfo=datetime.timezone.utc)
    return created_at >= since


def get_comments_with_mentions(pulls: list[tuple[Repository.Repository, PullRequest.PullRequest]], mention_keyword, since=None) -> list[TableRow]:
    result = []
    mention = re.compile(r"(?<![\w-])" + re.escape(mention_keyword) + r"(?![\w-])")
    for repo, pull in pulls:
        for comment in get_comments(pull):
            # REST comments do not expose thread resolution status.
            if is_recent(comment.created_at, since) and mention.search(comment.body or ""):
                result.append(
                    TableRow.from_dict({
                        "repo_id": repo.id,
                        "pr_id": pull.id,
                        "url": comment.html_url,
                        "pr": f"[link={pull.html_url}]{escape(pull.title)}[/link]",
                        "repo": f"[link={repo.html_url}]{escape(repo.name)}[/link]",
                        "date": str(comment.created_at.date()),
                        "state": "MENTIONED",
                        "comment": f"[link={comment.html_url}]{escape(comment.body[:50])}[/link]",
                        "row": ["pr", "repo", "date", "state", "comment"]
                    })
                )

    return result


def get_open_pulls_missing_response(pulls: list[tuple[Repository.Repository, PullRequest.PullRequest]], user_id, since=None) -> list[TableRow]:
    result = []

    for repo, pull in pulls:
        if not is_recent(pull.created_at, since) or pull.user.id == user_id:
            continue
        responded = False
        for comment in get_comments(pull):
            if comment.user is not None and comment.user.id == user_id:
                responded = True

        if not responded:
            responded = any(
                review.user is not None
                and review.user.id == user_id
                and review.state != "PENDING"
                for review in pull.get_reviews()
            )

        if not responded:
            result.append(
                TableRow.from_dict({
                    "repo_id": repo.id,
                    "pr_id": pull.id,
                    "url": pull.html_url,
                    "pr": f"[link={pull.html_url}]{escape(pull.title)}[/link]",
                    "repo": f"[link={repo.html_url}]{escape(repo.name)}[/link]",
                    "date": str(pull.created_at.date()),
                    "state": "UNRESPONDED",
                    "comment": None,
                    "row": ["pr", "repo", "date", "state", "comment"]
                })
            )

    return result


def get_my_open_pulls(pulls: list[tuple[Repository.Repository, PullRequest.PullRequest]], user_id) -> list[TableRow]:
    result = []

    for repo, pull in pulls:
        if pull.user.id == user_id:
            result.append(
                TableRow.from_dict({
                    "repo_id": repo.id,
                    "pr_id": pull.id,
                    "url": pull.html_url,
                    "pr": f"[link={pull.html_url}]{escape(pull.title)}[/link]",
                    "repo": f"[link={repo.html_url}]{escape(repo.name)}[/link]",
                    "date": str(pull.created_at.date()),
                    "state": "MINE",
                    "comment": None,
                    "row": ["pr", "repo", "date", "state", "comment"]
                })
            )

    return result


def make_table():
    table = Table(title="Pulls")

    table.add_column("PR")
    table.add_column("Repo", style="magenta")
    table.add_column("Date", justify="right", style="cyan", no_wrap=True)
    table.add_column("State", style="magenta")
    table.add_column("Comment", style="green")

    return table


def print_table(table, rows: list[TableRow], selected=0):
    for i, row in enumerate(rows):
        row_vals = [getattr(row, k) for k in row.row]
        if i == selected:
            table.add_row(*row_vals, style=SELECTED)
        else:
            table.add_row(*row_vals)

    return table


def prioritize_rows(*groups):
    rows = {}
    for group in groups:
        for row in sorted(group, key=lambda row: (row.date, row.repo_id, row.pr_id, row.url), reverse=True):
            rows.setdefault((row.repo_id, row.pr_id), row)
    return list(rows.values())


@click.command()
def main():
    hostname = os.getenv("SETOOLKIT_GITHUB_HOSTNAME")
    access_token = os.getenv("SETOOLKIT_GITHUB_ACCESS_TOKEN")
    since_override = os.getenv("SETOOLKIT_GPR_SINCE")

    if not access_token:
        raise click.ClickException("Set SETOOLKIT_GITHUB_ACCESS_TOKEN to a GitHub access token.")
    auth = Auth.Token(access_token)
    base_url = f"https://{hostname}/api/v3" if hostname and hostname != "github.com" else Consts.DEFAULT_BASE_URL

    if since_override:
        try:
            some_time_ago = parser.parse(since_override)
        except (ValueError, OverflowError) as error:
            raise click.ClickException("SETOOLKIT_GPR_SINCE must be a valid date.") from error
    else:
        some_time_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(weeks=4)

    g = Github(auth=auth, base_url=base_url)
    try:
        user = g.get_user()
        pulls = list(get_open_pulls(user.get_repos()))
        items = prioritize_rows(
            get_comments_with_mentions(pulls, f"@{user.login}", since=some_time_ago),
            get_my_open_pulls(pulls, user.id),
            get_open_pulls_missing_response(pulls, user.id, since=some_time_ago),
        )
        if not items:
            print("No results")
            return

        selected = 0
        with Live(print_table(make_table(), items, selected), auto_refresh=False) as live:
            while True:
                selected_data = items[selected]
                match readkey():
                    case key.UP | "k":
                        selected = max(0, selected - 1)
                    case key.DOWN  | "j":
                        selected = min(len(items) - 1, selected + 1)
                    case key.ENTER:
                        # prevents an extra line from printing on stop
                        webbrowser.open_new_tab(selected_data.url)

                live.update(print_table(make_table(), items, selected), refresh=True)
    except KeyboardInterrupt:
        pass
    finally:
        g.close()


if __name__ == "__main__":
    main()
