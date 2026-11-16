"""Validate skill metadata and references when the skill is present."""

from pathlib import Path
import re
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless((ROOT / "SKILL.md").is_file(), "Skill not included in this revision")
class SkillManifestTests(unittest.TestCase):
    def test_manifest_has_agent_skills_metadata(self):
        source = (ROOT / "SKILL.md").read_text()
        sections = source.split("---", 2)
        self.assertEqual(sections[0], "")
        metadata = yaml.safe_load(sections[1])
        self.assertEqual(metadata["name"], "setoolkit")
        self.assertTrue(metadata["description"].strip())

    def test_local_reference_links_resolve(self):
        source = (ROOT / "SKILL.md").read_text()
        links = re.findall(r"\]\((references/[^)]+)\)", source)
        self.assertTrue(links, "Expected bundled references")
        for link in links:
            with self.subTest(link=link):
                self.assertTrue((ROOT / link).is_file())

    def test_evaluation_cases_have_valid_metadata_and_graders(self):
        cases = list((ROOT / "evals").glob("*/case.yaml"))
        self.assertTrue(cases)
        for path in cases:
            with self.subTest(case=path.parent.name):
                metadata = yaml.safe_load(path.read_text())
                self.assertEqual(metadata["schema_version"], "1.1")
                self.assertEqual(metadata["name"], path.parent.name)
                self.assertTrue((path.parent / "prompt.md").is_file())
                self.assertTrue(list((path.parent / "graders").glob("*.md")))
