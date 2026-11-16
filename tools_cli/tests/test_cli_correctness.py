import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from click.testing import CliRunner
from git import Repo, exc

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
import gcs
import gst
import qs
import rt
from s3u2u import s3_to_console_url


class QuietLive:
    def __init__(self, *args, **kwargs):
        self.console = SimpleNamespace(clear=lambda: None)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def update(self, *args, **kwargs):
        pass

    def stop(self):
        pass

    def start(self):
        pass


class StashTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "repo"
        self.repo = Repo.init(self.path)
        self.addCleanup(self.repo.close)
        with self.repo.config_writer() as config:
            config.set_value("user", "name", "Test User")
            config.set_value("user", "email", "test@example.invalid")
        self.file = self.path / "file.txt"
        self.file.write_text("base\n")
        self.repo.index.add(["file.txt"])
        self.repo.index.commit("base")

    def stash(self, value):
        self.file.write_text(value)
        self.repo.git.stash("push", "-m", value)
        return self.repo.commit("stash@{0}")

    def invoke(self, keys):
        with patch.object(gst, "get_project_from_path", return_value=self.path), patch.object(gst, "Live", QuietLive), patch.object(gst, "readkey", side_effect=keys):
            return CliRunner().invoke(gst.main)

    def test_rename_keeps_staged_unstaged_and_untracked_work(self):
        original = self.stash("first")
        other = self.stash("second")
        self.file.write_text("staged")
        self.repo.index.add(["file.txt"])
        self.file.write_text("unstaged")
        untracked = self.path / "untracked.txt"
        untracked.write_text("untracked")
        before = (self.repo.git.diff(), self.repo.git.diff("--cached"), self.repo.git.status("--porcelain"))

        gst.save_stash_name(self.repo, original.hexsha, "renamed")

        after = (self.repo.git.diff(), self.repo.git.diff("--cached"), self.repo.git.status("--porcelain"))
        self.assertEqual(before, after)
        self.assertEqual(untracked.read_text(), "untracked")
        renamed = self.repo.commit("stash@{0}")
        self.assertEqual(renamed.tree, original.tree)
        self.assertEqual(renamed.parents, original.parents)
        self.assertEqual(self.repo.commit("stash@{1}"), other)
        self.assertEqual(len(self.repo.git.stash("list").splitlines()), 2)

    def test_top_stash_can_be_renamed_and_applied(self):
        original = self.stash("saved contents")
        gst.save_stash_name(self.repo, original.hexsha, "new name")
        self.assertEqual(self.repo.git.stash("list", "--format=%gs"), "new name")
        gst.apply_stash(self.repo, 0)
        self.assertEqual(self.file.read_text(), "saved contents")

    def test_rename_store_failure_retains_original(self):
        original = self.stash("saved contents")
        lock = Path(self.repo.git_dir) / "refs/stash.lock"
        lock.write_text("")
        with self.assertRaises(exc.GitCommandError):
            gst.save_stash_name(self.repo, original.hexsha, "new name")
        self.assertEqual(self.repo.commit("stash@{0}"), original)

    def test_rename_preserves_untracked_files_inside_stash(self):
        untracked = self.path / "untracked.txt"
        untracked.write_text("saved untracked content")
        self.repo.git.stash("push", "-u", "-m", "original")
        original = self.repo.commit("stash@{0}")
        gst.save_stash_name(self.repo, original.hexsha, "renamed")
        self.assertEqual(self.repo.commit("stash@{0}").parents, original.parents)
        gst.apply_stash(self.repo, 0)
        self.assertEqual(untracked.read_text(), "saved untracked content")

    def test_stale_selection_does_not_pop_a_different_stash(self):
        selected = self.stash("selected")
        newer = self.stash("created after selection")
        with self.assertRaisesRegex(Exception, "stash list changed"):
            gst.apply_stash(self.repo, 0, selected.hexsha)
        self.assertEqual(self.repo.commit("stash@{0}"), newer)
        self.assertEqual(self.file.read_text(), "base\n")

    def test_empty_stash_list(self):
        result = self.invoke([])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("No stashes", result.output)

    def test_rename_key_uses_selected_stash(self):
        self.stash("old")
        with patch.object(gst.Prompt, "ask", return_value="new name"):
            result = self.invoke(["r", KeyboardInterrupt])
        self.assertEqual(result.exit_code, 0, result.exception)
        self.assertEqual(self.repo.git.stash("list", "--format=%gs"), "new name")

    def test_pop_last_stash_exits_cleanly(self):
        self.stash("saved")
        with patch.object(gst.Confirm, "ask", return_value=True):
            result = self.invoke(["a"])
        self.assertEqual(result.exit_code, 0, result.exception)
        self.assertEqual(self.repo.git.stash("list"), "")

    def test_pop_selected_last_row_clamps_selection(self):
        self.stash("first")
        self.stash("second")
        with patch.object(gst.Confirm, "ask", return_value=True):
            result = self.invoke([gst.key.DOWN, "a", KeyboardInterrupt])
        self.assertEqual(result.exit_code, 0, result.exception)
        self.assertEqual(len(self.repo.git.stash("list").splitlines()), 1)

    def test_worktree_from_subdirectory_uses_repo_root(self):
        self.repo.create_head("feature")
        subdir = self.path / "nested"
        subdir.mkdir()
        trees = Path(self.temp.name) / "trees"
        with patch.object(gcs, "TREES_PATH", trees), patch.object(gcs.pathlib.Path, "cwd", return_value=subdir):
            result = CliRunner().invoke(gcs.main, ["--branch-name", "feature"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((trees / "repo|feature" / "file.txt").is_file())


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.output = self.root / "selection"

    def invoke_qs(self, keys):
        with patch.object(qs, "get_project_from_path", return_value=self.root), patch.object(qs, "Live", QuietLive), patch.object(qs, "readkey", side_effect=keys):
            return CliRunner().invoke(qs.main, ["project", "--output", str(self.output)])

    def test_no_matches_exits_without_reading_input(self):
        result = self.invoke_qs([])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("No projects", result.output)
        self.assertFalse(self.output.exists())

    def test_cancel_is_unsuccessful_and_does_not_write_selection(self):
        (self.root / "autoci.json").write_text("{}")
        result = self.invoke_qs([KeyboardInterrupt])
        self.assertNotEqual(result.exit_code, 0)
        self.assertFalse(self.output.exists())

    def test_selection_writes_requested_file(self):
        project = self.root / "project with spaces"
        project.mkdir()
        (project / "autoci.json").write_text("{}")
        result = self.invoke_qs([qs.key.ENTER])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.output.read_text(), str(project))

    def test_missing_configuration_is_actionable(self):
        result = CliRunner().invoke(rt.main, env={"SETOOLKIT_CODE_PATH": None})
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Set SETOOLKIT_CODE_PATH", result.output)

    def test_worktree_path_expands_home(self):
        self.assertEqual(gcs.TREES_PATH, (Path.home() / ".config/tools/gcs/trees").resolve())

    def test_s3_url_preserves_special_characters(self):
        key = "folder/a&b#c +東京.csv"
        url = urlsplit(s3_to_console_url(f"s3://bucket/{key}", region="eu-west-1"))
        self.assertEqual(url.netloc, "eu-west-1.console.aws.amazon.com")
        self.assertEqual(parse_qs(url.query), {"region": ["eu-west-1"], "prefix": [key]})
        self.assertEqual(url.fragment, "")

    def test_shell_wrappers_quote_paths_and_clean_result_files(self):
        destination = self.root / "project with spaces"
        destination.mkdir()
        init = Path(__file__).parents[1] / "init.sh"
        script = '''
source "$INIT"
function ,print_rt() { printf '%s' "$DESTINATION"; return "$HELPER_STATUS"; }
function ,print_qs() {
    [ "$1" = "--output" ] || return 9
    [ "$3" = "my project" ] || return 8
    printf '%s\n' "$2" >> "$RESULT_LOG"
    printf '%s' "$DESTINATION" > "$2"
    return "$HELPER_STATUS"
}
if [ "$COMMAND" = "rt" ]; then ,rt; else ,qs "my project"; fi
exit_code=$?
printf '%s\n%s\n' "$exit_code" "$PWD"
'''
        for shell in ["bash", "zsh"]:
            executable = shutil.which(shell)
            if not executable:
                continue
            for command in ["rt", "qs"]:
                for status in [0, 7]:
                    with self.subTest(shell=shell, command=command, status=status):
                        log = self.root / "result-paths"
                        log.unlink(missing_ok=True)
                        env = dict(os.environ, INIT=str(init), DESTINATION=str(destination), HELPER_STATUS=str(status), COMMAND=command, RESULT_LOG=str(log), TMPDIR=str(self.root))
                        result = subprocess.run([executable, "-c", script], cwd=self.root, env=env, text=True, capture_output=True, timeout=10)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        expected = destination if status == 0 else self.root
                        self.assertEqual(result.stdout.splitlines(), [str(status), str(expected)])
                        if log.exists():
                            self.assertTrue(all(not Path(path).exists() for path in log.read_text().splitlines()))
