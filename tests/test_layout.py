"""Tests for the repository layout: what an install ships, and what the skills may refer to.

The skills and the command center share this repository (command-center/D13). Installing the plugin must still
ship only the skills (D16), and nothing under plugin/ may read, call or assume the app or the services, so a loop
always runs from a terminal alone (D14).

Run from the repository root: python3 -m unittest discover -s tests -v
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugin")
CHECK = os.path.join(ROOT, "scripts", "check.sh")
INSTALL = os.path.join(ROOT, "scripts", "install.sh")
IGNORED = {".DS_Store"}


def listdir(path):
    return sorted(name for name in os.listdir(path) if name not in IGNORED)


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


class PluginLayoutTest(unittest.TestCase):
    def test_marketplace_installs_the_plugin_folder(self):
        with open(os.path.join(ROOT, ".claude-plugin", "marketplace.json")) as f:
            market = json.load(f)
        self.assertEqual([p["source"] for p in market["plugins"]], ["./plugin"])
        self.assertFalse(os.path.exists(os.path.join(ROOT, ".claude-plugin", "plugin.json")),
                         "a root plugin.json would make the whole repository a plugin")

    def test_plugin_folder_holds_only_the_manifest_and_skills(self):
        self.assertEqual(listdir(PLUGIN), [".claude-plugin", "skills"])
        self.assertEqual(listdir(os.path.join(PLUGIN, ".claude-plugin")), ["plugin.json"])
        with open(os.path.join(PLUGIN, ".claude-plugin", "plugin.json")) as f:
            self.assertEqual(json.load(f)["name"], "architect-loop")

    def test_every_skill_is_a_loop_skill(self):
        skills = listdir(os.path.join(PLUGIN, "skills"))
        self.assertTrue(skills)
        for name in skills:
            self.assertTrue(name.startswith("loop-"), name)
            self.assertTrue(os.path.isfile(os.path.join(PLUGIN, "skills", name, "SKILL.md")), name)


@unittest.skipUnless(shutil.which("sh"), "needs sh")
class InstallTest(unittest.TestCase):
    def test_install_copies_exactly_the_skills(self):
        dest = tempfile.mkdtemp(prefix="install-")
        self.addCleanup(shutil.rmtree, dest)
        subprocess.run(["sh", INSTALL, "--dest", dest], check=True, capture_output=True, text=True)
        self.assertEqual(listdir(dest), listdir(os.path.join(PLUGIN, "skills")))


@unittest.skipUnless(shutil.which("sh"), "needs sh")
class IndependenceCheckTest(unittest.TestCase):
    """scripts/check.sh fails when a skill refers to the app or the services (D14)."""

    SKILL = "---\nname: loop-x\ndescription: A test skill.\n---\n# loop-x\n\n{body}\n"

    def run_check(self, body):
        root = tempfile.mkdtemp(prefix="check-")
        self.addCleanup(shutil.rmtree, root)
        os.makedirs(os.path.join(root, "scripts"))
        shutil.copy(CHECK, os.path.join(root, "scripts", "check.sh"))
        write(root, "plugin/skills/loop-x/SKILL.md", self.SKILL.format(body=body))
        return subprocess.run(["sh", os.path.join(root, "scripts", "check.sh")], capture_output=True, text=True)

    def test_a_clean_skill_passes(self):
        result = self.run_check("Read `docs/loops/` and the web-app/ folder named in touches.")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("ok   independence", result.stdout)

    def test_a_reference_to_the_app_fails(self):
        result = self.run_check("Then open app/src/features/inbox/ to show the card.")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAIL independence", result.stdout)
        self.assertIn("plugin/skills/loop-x/SKILL.md", result.stdout)

    def test_a_reference_to_the_services_fails(self):
        result = self.run_check("Post the verdict to ../services/status/ when it runs.")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAIL independence", result.stdout)

    def test_the_repository_itself_passes(self):
        result = subprocess.run(["sh", CHECK], capture_output=True, text=True, env={**os.environ, "CHECK_SKIP_TESTS": "1"})
        self.assertIn("ok   independence", result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
