import datetime
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
import gpr


class PullRequestTests(unittest.TestCase):
    def setUp(self):
        self.since = datetime.datetime(2026, 10, 1, tzinfo=datetime.timezone.utc)
        self.old = datetime.datetime(2026, 9, 1, tzinfo=datetime.timezone.utc)
        self.recent = datetime.datetime(2026, 11, 1, tzinfo=datetime.timezone.utc)
        self.repo = SimpleNamespace(id=1, name="repo", html_url="https://github.com/test/repo")
        self.pull = SimpleNamespace(id=2, title="PR [brackets]", html_url="https://github.com/test/repo/pull/2", created_at=self.recent, user=SimpleNamespace(id=456), get_reviews=Mock(return_value=[]))
        self.pulls = [(self.repo, self.pull)]

    def comment(self, body="@me please review", created_at=None, user_id=456):
        return SimpleNamespace(body=body, created_at=created_at or self.recent, html_url="https://github.com/test/repo/pull/2#comment", user=SimpleNamespace(id=user_id))

    def test_mentions_respect_since_and_exact_username(self):
        comments = [self.comment(created_at=self.old), self.comment(body="@me-too @me2"), self.comment(body="hello @me!")]
        with patch.object(gpr, "get_comments", return_value=comments):
            rows = gpr.get_comments_with_mentions(self.pulls, "@me", since=self.since)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].state, "MENTIONED")
        self.assertIn("hello @me!", rows[0].comment)
        self.assertIn(self.repo.html_url, rows[0].repo)

    def test_naive_cutoff_compares_with_aware_dates(self):
        self.assertTrue(gpr.is_recent(self.recent, self.since.replace(tzinfo=None)))
        self.assertFalse(gpr.is_recent(self.old.replace(tzinfo=None), self.since))

    def test_submitted_review_counts_as_response(self):
        for state in ["APPROVED", "CHANGES_REQUESTED", "COMMENTED"]:
            with self.subTest(state=state):
                self.pull.get_reviews.return_value = [SimpleNamespace(user=SimpleNamespace(id=123), state=state)]
                with patch.object(gpr, "get_comments", return_value=[]):
                    self.assertEqual(gpr.get_open_pulls_missing_response(self.pulls, 123, self.since), [])

    def test_pending_review_does_not_count_as_response(self):
        self.pull.get_reviews.return_value = [SimpleNamespace(user=SimpleNamespace(id=123), state="PENDING")]
        with patch.object(gpr, "get_comments", return_value=[]):
            self.assertEqual(len(gpr.get_open_pulls_missing_response(self.pulls, 123, self.since)), 1)

    def test_comment_counts_as_response(self):
        with patch.object(gpr, "get_comments", return_value=[self.comment(user_id=123)]):
            self.assertEqual(gpr.get_open_pulls_missing_response(self.pulls, 123, self.since), [])
        self.pull.get_reviews.assert_not_called()

    def test_old_pr_is_excluded_before_fetching_comments(self):
        self.pull.created_at = self.old
        with patch.object(gpr, "get_comments") as comments:
            self.assertEqual(gpr.get_open_pulls_missing_response(self.pulls, 123, self.since), [])
        comments.assert_not_called()

    def test_own_old_pr_is_still_included_as_mine(self):
        self.pull.created_at = self.old
        self.pull.user.id = 123
        self.assertEqual(gpr.get_my_open_pulls(self.pulls, 123)[0].state, "MINE")

    def row(self, pr_id, state, date):
        return gpr.TableRow(1, pr_id, f"https://example.com/{pr_id}", "title", "repo", date, state, None, [])

    def test_priority_deduplication_and_date_order(self):
        mentioned = self.row(1, "MENTIONED", "2026-10-01")
        older_mention = self.row(1, "MENTIONED", "2026-09-01")
        mine = self.row(2, "MINE", "2026-10-02")
        recent_mine = self.row(3, "MINE", "2026-11-02")
        waiting = self.row(4, "UNRESPONDED", "2026-11-10")
        rows = gpr.prioritize_rows([older_mention, mentioned], [mine, recent_mine, self.row(1, "MINE", "2026-11-01")], [waiting, self.row(2, "UNRESPONDED", "2026-11-10")])
        self.assertEqual(rows, [mentioned, recent_mine, mine, waiting])
        self.assertIs(rows[0], mentioned)

    def test_cli_no_results_closes_client_and_uses_public_api(self):
        client = Mock()
        client.get_user.return_value.get_repos.return_value = []
        with patch.object(gpr, "Github", return_value=client) as github:
            result = CliRunner().invoke(gpr.main, env={"SETOOLKIT_GITHUB_ACCESS_TOKEN": "test", "SETOOLKIT_GITHUB_HOSTNAME": "github.com", "SETOOLKIT_GPR_SINCE": "2026-10-01"})
        self.assertEqual(result.exit_code, 0, result.exception)
        self.assertIn("No results", result.output)
        self.assertEqual(github.call_args.kwargs["base_url"], gpr.Consts.DEFAULT_BASE_URL)
        client.close.assert_called_once()

    def test_invalid_configuration_does_not_call_github(self):
        for env in [{"SETOOLKIT_GITHUB_ACCESS_TOKEN": None}, {"SETOOLKIT_GITHUB_ACCESS_TOKEN": "test", "SETOOLKIT_GPR_SINCE": "not a date"}]:
            with self.subTest(env=env), patch.object(gpr, "Github") as github:
                result = CliRunner().invoke(gpr.main, env=env)
                self.assertNotEqual(result.exit_code, 0)
                github.assert_not_called()
