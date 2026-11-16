import dataclasses
import datetime
import dateutil
import functools
import itertools
import os
from typing import Literal
import webbrowser

from github import Github, Auth, Consts, Repository, PullRequest
from readchar import readkey, key
from rich.live import Live
from rich.style import Style
from rich.table import Table


SELECTED = Style(color="blue", bgcolor="white", bold=True)


@dataclasses.dataclass
class TableRow():
    repo_id: str
    pr_id: str
    url: str
    pr: str
    repo: str
    date: str
    state: Literal["UNRESOLVED", "UNRESPONDED", "MINE"]
    comment: str
    row: list[str]

    def __eq__(self, other):
        return other and self.repo_id == other.repo_id and self.pr_id == other.pr_id

    def __ne__(self, other):
        return not self.__eq__(other)

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


def get_unresolved_comments_with_mentions(pulls: list[tuple[Repository.Repository, PullRequest.PullRequest]], mention_keyword, since=None) -> list[TableRow]:
    result = []
    for repo, pull in pulls:
        for comment in get_comments(pull):
            # there doesn't seem to be any way to filter out resolved comments
            if mention_keyword in comment.body:
                result.append(
                    TableRow.from_dict({
                        "repo_id": repo.id,
                        "pr_id": pull.id,
                        "url": comment.html_url,
                        "pr": f"[link={pull.html_url}]{pull.title}[/link]",
                        "repo": f"[link={repo.url}]{repo.name}[/link]",
                        "date": str(comment.created_at.date()),
                        "state": "UNRESOLVED",
                        "comment": f"[link={comment.html_url}]{comment.body[:50]}[/link]",
                        "row": ["pr", "repo", "date", "state", "comment"]
                    })
                )

    return result


def get_open_pulls_missing_response(pulls: list[tuple[Repository.Repository, PullRequest.PullRequest]], user_id, since=None) -> list[TableRow]:
    result = []

    for repo, pull in pulls:
        responded = False
        for comment in get_comments(pull):
            if comment.user.id == user_id:
                responded = True

        if not responded:
            result.append(
                TableRow.from_dict({
                    "repo_id": repo.id,
                    "pr_id": pull.id,
                    "url": pull.html_url,
                    "pr": f"[link={pull.html_url}]{pull.title}[/link]",
                    "repo": f"[link={repo.url}]{repo.name}[/link]",
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
                    "pr": f"[link={pull.html_url}]{pull.title}[/link]",
                    "repo": f"[link={repo.url}]{repo.name}[/link]",
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


def print_some_test_data(user):
    since = dateutil.parser.parse("2019-07-18")
    print(user.login)

    repo = user.get_repo("setoolkit")
    print(repo)
    for prc in repo.get_pulls_comments(since=since):
        print(prc.body)

    for pull in repo.get_pulls():
        for comment in pull.get_issue_comments():
            print(comment.body)

    for repo in user.get_repos():
        print(repo)
        for prc in repo.get_pulls_comments(since=since):
            print(prc)


def main():
    hostname = os.getenv("SETOOLKIT_GITHUB_HOSTNAME")
    access_token = os.getenv("SETOOLKIT_GITHUB_ACCESS_TOKEN")
    since_override = os.getenv("SETOOLKIT_GPR_SINCE")

    auth = Auth.Token(access_token)

    base_url = f"https://{hostname}/api/v3" if hostname else Consts.DEFAULT_BASE_URL
    g = Github(auth=auth, base_url=base_url)

    user = g.get_user()
    # print_some_test_data(user)

    if since_override:
        some_time_ago = dateutil.parser.parse(since_override)
    else:
        some_time_ago = datetime.datetime.now() - datetime.timedelta(weeks=4)

    repos = user.get_repos()
    pulls = list(get_open_pulls(repos))
    items = list(
        set(get_unresolved_comments_with_mentions(pulls, f"@{user.login}", since=some_time_ago))
        | set(get_my_open_pulls(pulls, user.id))
        | set(get_open_pulls_missing_response(pulls, user.id, since=some_time_ago))
    )
    if not items:
        print("No results")
        return

    selected = 0
    try:
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
