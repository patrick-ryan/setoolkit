import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
import uuid


spec = importlib.util.spec_from_file_location(
    "test_runner", Path(__file__).parents[1] / "scripts/run_tests.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class TestRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.output = io.StringIO()

    def add_test(self, directory, body="self.assertTrue(True)"):
        directory = self.root / directory
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"test_{uuid.uuid4().hex}.py"
        path.write_text(
            "import unittest\n"
            "class Example(unittest.TestCase):\n"
            "    def test_example(self):\n"
            f"        {body}\n"
        )
        return path

    def test_discovers_all_packages_without_package_init_files(self):
        for directory in runner.SUITES.values():
            self.add_test(directory)
        self.assertEqual(runner.run_tests(self.root, stream=self.output), 0)
        self.assertIn("Ran 3 tests", self.output.getvalue())

    def test_failure_returns_nonzero(self):
        self.add_test("db_lib/tests", "self.fail('regression')")
        self.assertEqual(runner.run_tests(self.root, stream=self.output), 1)
        self.assertIn("regression", self.output.getvalue())

    def test_import_error_is_not_treated_as_an_empty_suite(self):
        path = self.add_test("tools_cli/tests")
        path.write_text("raise ImportError('broken dependency')\n")
        self.assertEqual(runner.run_tests(self.root, stream=self.output), 1)
        self.assertIn("broken dependency", self.output.getvalue())

    def test_no_tests_returns_nonzero(self):
        self.assertEqual(runner.run_tests(self.root, stream=self.output), 2)
        self.assertIn("No tests discovered", self.output.getvalue())

    def test_selected_suite_does_not_run_other_package(self):
        self.add_test("db_lib/tests")
        self.add_test("tools_cli/tests", "self.fail('not selected')")
        self.assertEqual(runner.run_tests(self.root, selected="db", stream=self.output), 0)
        self.assertIn("Ran 1 test", self.output.getvalue())

    def test_missing_selected_suite_does_not_pass_due_to_other_tests(self):
        self.add_test("tests")
        self.assertEqual(runner.run_tests(self.root, selected="cli", stream=self.output), 2)
