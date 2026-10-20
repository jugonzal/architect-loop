"""Tests for plugin/skills/loop-init/scripts/migrate_gen1.py.

Each test builds a small synthetic generation 1 repository in a temporary directory: a few commits,
one of them a squash merge whose subject ends in "(#12)" and one a merge commit for PR #14, so that
`touches` inference runs against real git history. The proposals come from tests/fixtures/gen1/,
with `{SHA12}` and `{SHA14}` replaced by those commits' short SHAs.

Run from the repository root: python3 -m unittest discover -s tests -v
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "plugin", "skills", "loop-init", "scripts", "migrate_gen1.py")
FIXTURES = os.path.join(HERE, "fixtures", "gen1")
TODAY = "2026-10-17"

_spec = importlib.util.spec_from_file_location("migrate_gen1", SCRIPT)
mig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mig)


def git_env(home):
    env = dict(os.environ)
    env.update({
        "HOME": home,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Test Owner", "GIT_AUTHOR_EMAIL": "owner@example.test",
        "GIT_COMMITTER_NAME": "Test Owner", "GIT_COMMITTER_EMAIL": "owner@example.test",
        "GIT_AUTHOR_DATE": "2026-09-01T12:00:00Z", "GIT_COMMITTER_DATE": "2026-09-01T12:00:00Z",
    })
    return env


def git(repo, env, *args):
    r = subprocess.run(["git", "-c", "commit.gpgsign=false", "-C", repo] + list(args),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, env=env)
    if r.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), r.stderr))
    return r.stdout.strip()


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def read(root, rel):
    with open(os.path.join(root, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def make_repo(tmp):
    """A generation 1 repository with real history; returns (repo, env, shas)."""
    home = os.path.join(tmp, "home")
    os.makedirs(home)
    env = git_env(home)
    repo = os.path.join(tmp, "repo")
    os.makedirs(repo)
    git(repo, env, "init", "-q")
    git(repo, env, "symbolic-ref", "HEAD", "refs/heads/main")
    write(repo, "src/app.py", "print('widgets')\n")
    git(repo, env, "add", "-A")
    git(repo, env, "commit", "-q", "-m", "Start the widget app")
    # A squash merge: one commit whose subject ends in (#12).
    write(repo, "src/export.py", "def export():\n    return 'csv'\n")
    write(repo, "tests/test_export.py", "assert True\n")
    write(repo, "docs/proposals/alpha.md", "# Proposal: draft\n")
    git(repo, env, "add", "-A")
    git(repo, env, "commit", "-q", "-m", "Let users download their widgets as CSV (#12)")
    sha12 = git(repo, env, "rev-parse", "--short=7", "HEAD")
    # A merge commit for PR #14.
    git(repo, env, "checkout", "-q", "-b", "someone/admin-list")
    write(repo, "src/admin.py", "def exports():\n    return []\n")
    git(repo, env, "add", "-A")
    git(repo, env, "commit", "-q", "-m", "List the exports in the admin")
    git(repo, env, "checkout", "-q", "main")
    git(repo, env, "merge", "-q", "--no-ff", "-m", "Merge pull request #14 from someone/admin-list",
        "someone/admin-list")
    sha14 = git(repo, env, "rev-parse", "--short=7", "HEAD")
    # The generation 1 documents, with the real SHAs.
    for dirpath, _dirs, files in os.walk(FIXTURES):
        for name in files:
            src = os.path.join(dirpath, name)
            rel = os.path.relpath(src, FIXTURES)
            with open(src, "r", encoding="utf-8") as fh:
                text = fh.read().replace("{SHA12}", sha12).replace("{SHA14}", sha14)
            write(repo, rel, text)
    git(repo, env, "add", "-A")
    git(repo, env, "commit", "-q", "-m", "Record the proposals")
    return repo, env, {"12": sha12, "14": sha14}


def snapshot(repo):
    out = {}
    for dirpath, dirs, files in os.walk(repo):
        if ".git" in dirs:
            dirs.remove(".git")
        for name in files:
            path = os.path.join(dirpath, name)
            with open(path, "rb") as fh:
                out[os.path.relpath(path, repo)] = fh.read()
    return out


def front_matter(text):
    lines = text.split("\n")
    assert lines[0] == "---", text[:200]
    end = lines.index("---", 1)
    return "\n".join(lines[: end + 1])


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="migrate-gen1-")
        self.repo, self.env, self.shas = make_repo(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_script(self, *args, repo=None):
        r = subprocess.run([sys.executable, SCRIPT, "--repo", repo or self.repo, "--today", TODAY] + list(args),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, env=self.env)
        return r.returncode, r.stdout, r.stderr


class DryRunTest(Base):
    def test_dry_run_writes_nothing_and_shows_the_plan(self):
        before = snapshot(self.repo)
        code, out, err = self.run_script()
        self.assertEqual(code, 0, err)
        self.assertEqual(before, snapshot(self.repo))
        self.assertIn("DRY RUN", out)
        self.assertIn("MIGRATE  alpha", out)
        self.assertIn("MIGRATE  delta", out)
        self.assertIn("becomes a backlog loop", out)
        self.assertIn("HISTORY  beta", out)
        self.assertIn("HISTORY  gamma", out)
        self.assertIn("Ignored, no generation 1 Status line: notes.md", out)
        self.assertIn("concern list-exports.md", out)
        self.assertIn("Step 2 is a container for 2a, 2b", out)
        self.assertIn("[ignored heading]", out)
        self.assertIn("[no done-when] Step 4", out)
        self.assertIn("[unparsed proof] Step 2b", out)
        self.assertIn("Summary:", out)

    def test_reasons_are_printed(self):
        _code, out, _err = self.run_script()
        self.assertIn('done: Status starts with "done"', out)
        self.assertIn("done: on production and verified", out)
        self.assertIn('unfinished: Status says "not yet on production"', out)


class ApplyTest(Base):
    def setUp(self):
        super().setUp()
        code, self.out, err = self.run_script("--apply")
        self.assertEqual(code, 0, err)

    def test_writes_the_expected_files(self):
        loops = sorted(os.path.relpath(os.path.join(d, f), self.repo)
                       for d, _s, fs in os.walk(os.path.join(self.repo, "docs", "loops")) for f in fs)
        self.assertEqual(loops, sorted([
            "docs/loops/alpha/README.md",
            "docs/loops/alpha/cancel-export.md",
            "docs/loops/alpha/export-background.md",
            "docs/loops/alpha/list-exports.md",
            "docs/loops/alpha/show-progress-ui.md",
            "docs/loops/delta/README.md",
            "docs/loops/delta/store-tags-widgets.md",
        ]))
        self.assertIn("Files written (9):", self.out)

    def test_front_matter_is_exact(self):
        cases = {
            "list-exports": "---\nneeds: [alpha/D1]\ntouches: [src/admin.py]\neffects: []\n"
                            "ships-to: production\nprs: [14]\n---",
            "show-progress-ui": "---\nneeds: [list-exports]\ntouches: []\neffects: []\n"
                                "ships-to: production\nprs: [15]\n---",
            "export-background": "---\nneeds: [alpha/D3]\ntouches: []\neffects: [migration on shared data (owner).]\n"
                                 "ships-to: production\n---",
            "cancel-export": "---\nneeds: []\ntouches: []\neffects: []\nships-to: production\n---",
        }
        for slug, expected in cases.items():
            self.assertEqual(front_matter(read(self.repo, "docs/loops/alpha/%s.md" % slug)), expected, slug)

    def test_concern_body(self):
        text = read(self.repo, "docs/loops/alpha/list-exports.md")
        self.assertIn("\n# List the exports (D1)\n", text)
        self.assertIn("> Migrated from [`docs/proposals/alpha.md`](../../proposals/alpha.md) Step 2a on 2026-10-17; "
                      "its status then: \"built, merged #14; on staging (`%s`), verified 2026-09-29; not yet on "
                      "production\". Rewrite the title as an outcome in /loop-design." % self.shas["14"], text)
        self.assertIn("## Done when\n\n- **C1**\n  - the screen lists every export of the last 7 days;\n"
                      "  - an admin sees the size of each.\n", text)
        self.assertIn("### Approach\n\n- adds an Exports screen to the admin;\n- shows each export's size.\n", text)
        self.assertIn("## Decisions\n\n| # | Decision | Decided by, date | Closes |\n| --- | --- | --- | --- |\n", text)
        self.assertIn("## Questions\n\n| # | Question | Blocks | Default if unanswered |\n| --- | --- | --- | --- |\n",
                      text)
        self.assertTrue(text.endswith("## Shipped\n"))
        self.assertNotIn("<!--", text)
        sections = [l for l in text.split("\n") if l.startswith("#")]
        self.assertEqual(sections, ["# List the exports (D1)", "## Done when", "## Design", "### Where we are",
                                    "### Approach", "## Decisions", "## Questions", "## Evidence", "## Shipped"])

    def test_evidence_lines(self):
        sha = self.shas["14"]
        text = read(self.repo, "docs/loops/alpha/list-exports.md")
        self.assertIn("- 2026-09-29 · C1 · HOLDS · rung 1 · staging @%s · the list shows 3 "
                      "exports.\n" % sha, text)
        self.assertIn("- 2026-09-29 · C1 · UNPROVEN · rung ? · staging @%s · the sizes, "
                      "which need a real export. (commit and environment from the verdict before it)\n" % sha, text)
        progress = read(self.repo, "docs/loops/alpha/show-progress-ui.md")
        self.assertIn("- 2026-09-30 · C1 · UNPROVEN · rung ? · unknown @? · no build yet. "
                      "(migrated without a commit, so status does not count it)\n", progress)
        cancel = read(self.repo, "docs/loops/alpha/cancel-export.md")
        self.assertIn("## Evidence\n\nProof recorded in generation 1, verbatim, not counted by status: the owner "
                      "clicked it once on a laptop and it looked fine.\n", cancel)
        background = read(self.repo, "docs/loops/alpha/export-background.md")
        self.assertIn("## Evidence\n\n## Shipped\n", background)
        self.assertIn("- **C1** TODO(owner): this step had no \"done when\".", background)

    def test_readme(self):
        text = read(self.repo, "docs/loops/alpha/README.md")
        self.assertTrue(text.startswith("# Let users export their widgets\n\n> Migrated from "
                                        "[`docs/proposals/alpha.md`](../../proposals/alpha.md) on 2026-10-17 by "
                                        "migrate_gen1.py. That file is now history. Done steps stay there; "
                                        "unfinished steps became the concerns in this folder.\n"), text[:400])
        self.assertIn("**Intent.** Users cannot get their widgets out of the app.", text)
        self.assertIn("**Non-goals.** importing widgets back.\n", text)
        self.assertIn("## Goals\n\n- **G1** A user downloads every widget as CSV, verified on production.\n"
                      "- **G2 Fast.** The export of 1000 widgets takes under 2 s.\n  Measured on staging, 20 runs.\n",
                      text)
        self.assertIn("## Relations\n\n- Not compared with other loops yet. Run /loop-design alpha to record "
                      "relations.\n", text)
        self.assertIn("## Where we are\n\nSee the history file's \"Where we actually are\" section, as of "
                      "2026-09-30. Verify before relying on it.\n", text)
        self.assertIn("| D1 | CSV, not JSON | owner, 2026-09-20 | Closes Q1 |\n"
                      "| ~~D2~~ | ~~Export synchronously~~ → D3 | owner, 2026-09-21 | |\n"
                      "| D3 | Export through the job queue | owner, 2026-09-22 | Supersedes D2 |\n", text)
        self.assertIn("### Defaults this loop assumes (veto any)\n\n- The file name carries the date.\n"
                      "- Exports expire after 7 days.\n", text)
        self.assertIn("| Q2 | Include deleted widgets? | Step 4 | No |\n", text)
        self.assertIn("## Evidence\n\n## Shipped\n", text)
        self.assertIn("- Step 0, Spike the CSV writer: done, 2026-09-21\n", text)
        self.assertIn("- Step 1, Add the export endpoint (per D1): built, merged #12; on staging (`%s`) and production "
                      "(`%s`), verified 2026-09-28\n" % (self.shas["12"], self.shas["12"]), text)
        headings = [l for l in text.split("\n") if l.startswith("## ")]
        self.assertEqual(headings, ["## Goals", "## Relations", "## Where we are", "## Shared decisions",
                                    "## Questions", "## Evidence", "## Shipped"])
        self.assertNotIn("<!--", text)
        self.assertTrue(text.endswith("\n") and not text.endswith("\n\n"))

    def test_history_file_marked_once(self):
        lines = read(self.repo, "docs/proposals/alpha.md").split("\n")
        self.assertTrue(lines[2].startswith("**Status:** In progress"))
        self.assertEqual(lines[3], "the progress bar are open.")
        self.assertEqual(lines[4], "**Migrated:** to [`docs/loops/alpha/`](../loops/alpha/) on 2026-10-17. This "
                                   "document is history; the loop skills no longer track it.")
        self.assertTrue(lines[5].startswith("**Area:**"))
        self.assertEqual(sum(1 for l in lines if l.startswith("**Migrated:**")), 1)
        self.assertNotIn("**Migrated:**", read(self.repo, "docs/proposals/beta.md"))
        self.assertNotIn("**Migrated:**", read(self.repo, "docs/proposals/notes.md"))

    def test_second_apply_changes_nothing(self):
        before = snapshot(self.repo)
        code, out, err = self.run_script("--apply")
        self.assertEqual(code, 0, err)
        self.assertEqual(before, snapshot(self.repo))
        self.assertIn("already migrated (docs/loops/alpha/ exists)", out)
        self.assertIn("Files written (0):", out)

    def test_loop_md_is_untouched_and_reported(self):
        self.assertEqual(read(self.repo, "LOOP.md"), read(FIXTURES, "LOOP.md"))
        self.assertIn("remove the generation 1 proposal Status table", self.out)
        self.assertIn('remove the "Plan step status" convention', self.out)
        self.assertIn("add the Loops line", self.out)
        self.assertIn("add the default row that lets agents merge loop-document PRs", self.out)
        self.assertIn('add the "Served commit: a command that prints its SHA" column', self.out)
        self.assertIn("fill the `<command>` placeholders", self.out)


class OptionsTest(Base):
    def test_only_restricts_and_forces_history(self):
        code, out, err = self.run_script("--apply", "--only", "gamma")
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.isfile(os.path.join(self.repo, "docs/loops/gamma/README.md")))
        self.assertTrue(os.path.isfile(os.path.join(self.repo, "docs/loops/gamma/signed-links.md")))
        self.assertFalse(os.path.exists(os.path.join(self.repo, "docs/loops/alpha")))
        self.assertFalse(os.path.exists(os.path.join(self.repo, "docs/loops/delta")))
        self.assertIn("because --only names it", out)
        self.assertTrue(read(self.repo, "docs/loops/gamma/README.md").startswith("# Widget sharing\n"))
        self.assertIn("**Migrated:**", read(self.repo, "docs/proposals/gamma.md"))
        self.assertNotIn("**Migrated:**", read(self.repo, "docs/proposals/alpha.md"))

    def test_only_unknown_slug_warns(self):
        code, out, _err = self.run_script("--only", "nope")
        self.assertEqual(code, 0)
        self.assertIn("--only nope matches no generation 1 proposal", out)

    def test_include_done_and_squash_touches(self):
        code, _out, err = self.run_script("--apply", "--include-done", "--only", "alpha")
        self.assertEqual(code, 0, err)
        endpoint = read(self.repo, "docs/loops/alpha/add-export-endpoint.md")
        self.assertEqual(front_matter(endpoint), "---\nneeds: [alpha/D1]\ntouches: [src/export.py, "
                                                 "tests/test_export.py]\neffects: []\nships-to: production\n"
                                                 "prs: [12]\n---")
        self.assertIn("- 2026-09-28 · C1 · HOLDS · rung 1 · production @%s · the download "
                      "worked.\n" % self.shas["12"], endpoint)
        spike = read(self.repo, "docs/loops/alpha/spike-csv-writer.md")
        self.assertIn("- 2026-09-21 · C1 · HOLDS · rung 4 · local @? · 0.4 s for 1000 rows. "
                      "(migrated without a commit, so status does not count it)\n", spike)
        background = read(self.repo, "docs/loops/alpha/export-background.md")
        self.assertIn("needs: [add-export-endpoint, alpha/D3]", background)

    def test_no_mark(self):
        code, _out, err = self.run_script("--apply", "--no-mark")
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.isfile(os.path.join(self.repo, "docs/loops/alpha/README.md")))
        self.assertEqual(read(self.repo, "docs/proposals/alpha.md").count("**Migrated:**"), 0)

    def test_old_skills_report(self):
        home = self.env["HOME"]
        write(home, ".claude/skills/loop-frame/SKILL.md", "---\nname: loop-frame\n---\nThe old one.\n")
        write(home, ".claude/skills/loop-decide/SKILL.md", "---\nname: loop-decide\ndescription: Retired in "
                                                           "architect-loop 0.2.\n---\n")
        write(self.repo, ".claude/skills/loop-record/SKILL.md", "---\nname: loop-record\n---\nOld.\n")
        _code, out, _err = self.run_script()
        self.assertIn(os.path.join(home, ".claude", "skills", "loop-frame"), out)
        self.assertNotIn(os.path.join(home, ".claude", "skills", "loop-decide"), out)
        self.assertIn(os.path.join(self.repo, ".claude", "skills", "loop-record"), out)
        self.assertIn("generation 1 copies", out)

    def test_without_loop_md(self):
        os.remove(os.path.join(self.repo, "LOOP.md"))
        code, out, _err = self.run_script()
        self.assertEqual(code, 0)
        self.assertIn("There is no LOOP.md. Run /loop-init", out)
        self.assertIn('top environment "production"', out)


class ErrorsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="migrate-gen1-")
        self.env = git_env(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_script(self, repo, *args):
        r = subprocess.run([sys.executable, SCRIPT, "--repo", repo] + list(args), stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, universal_newlines=True, env=self.env)
        return r.returncode, r.stdout, r.stderr

    def test_not_a_git_repository(self):
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(os.path.join(plain, "docs", "proposals"))
        code, _out, err = self.run_script(plain)
        self.assertEqual(code, 2)
        self.assertIn("not a git repository", err)

    def test_no_proposals_folder(self):
        repo = os.path.join(self.tmp, "repo")
        os.makedirs(repo)
        git(repo, self.env, "init", "-q")
        code, _out, err = self.run_script(repo)
        self.assertEqual(code, 2)
        self.assertIn("no generation 1 proposals folder", err)

    def test_bad_date(self):
        code, _out, err = self.run_script(self.tmp, "--today", "17/10/2026")
        self.assertEqual(code, 2)
        self.assertIn("--today", err)


def make_step(status_lines):
    step = mig.Step("Step", "1", "A step", 3, 0)
    step.fields.append(("status", "", list(status_lines)))
    return step


class UnitTest(unittest.TestCase):
    def assertDone(self, lines, expected, top="production"):
        if isinstance(lines, str):
            lines = [lines]
        done, reason = mig.classify(make_step(lines), top)
        self.assertEqual(done, expected, "%r -> %s" % (lines, reason))

    def test_classify(self):
        self.assertDone("done, 2026-09-21", True)
        self.assertDone("Done 2026-09-21; nothing left", True)
        self.assertDone("built, merged #12; on staging (`abc1234`) and production (`abc1234`), verified 2026-09-28",
                        True)
        self.assertDone("built, merged #14; on staging (`abc1234`), verified 2026-09-29; not yet on production", False)
        self.assertDone("on production (`abc1234`), verified 2026-10-01. The cold read is not run yet", False)
        self.assertDone("built, merged #9; on staging and production (`abc1234`, flag off)", False)
        self.assertDone("on production (`abc1234`, flag off; verified 2026-10-02: the route answers 404)", False)
        self.assertDone("on staging (`abc1234`), verified 2026-10-02; on production (`abc1234`)", False)
        self.assertDone("in progress on `feat/x` (#15)", False)
        self.assertDone("not started", False)
        self.assertDone(["in progress.", "  - slice a merged in #3", "  - **Step 1: done 2026-10-04.**"], True)
        self.assertDone("on prod (`abc1234`), verified 2026-10-02", True, top="prod")
        # Half done stays tracked: a scope qualifier, or a marker that something is still waiting.
        self.assertDone("done for the web, 2026-01-16; the app waits for a store account", False)
        self.assertDone("done, 2026-01-16, but the export is not yet built", False)
        self.assertDone("done 2026-01-07, accepted by the owner; two items are still unproven", True)
        self.assertFalse(mig.classify(mig.Step("Step", "1", "t", 3, 0), "production")[0])

    def test_slugify(self):
        self.assertEqual(mig.slugify("Add the export endpoint (per D1)"), "add-export-endpoint")
        self.assertEqual(mig.slugify("The owner’s report, the admin’s view and the export list (web; X1)"),
                         "owner-report-admin-view-export-list")
        self.assertEqual(mig.slugify("Crème brûlée in a café"), "creme-brulee-cafe")
        long = mig.slugify("Reconcile extraordinarily complicated multitenant authorization hierarchies everywhere")
        self.assertLessEqual(len(long), 50)
        self.assertLessEqual(len(long.split("-")), 6)

    def test_collapse_touches(self):
        few = ["src/a.py", "src/b.py", "README.md"]
        self.assertEqual(mig.collapse_touches(few), few)
        many = ["src/a/1.py", "src/a/2.py", "src/b/3.py", "src/b/4.py", "lib/x.py", "lib/y.py", "README.md",
                "tests/t1.py"]
        self.assertEqual(sorted(mig.collapse_touches(many)),
                         sorted(["src/a/**", "src/b/**", "lib/**", "README.md", "tests/**"]))
        deep = ["a/%d/x.py" % i for i in range(8)]
        self.assertEqual(mig.collapse_touches(deep), ["a/**"])
        # A glob never covers docs/loops/ or the proposals folder, or status would see every
        # loop-document PR as a change under touches.
        docs = ["docs/api.md", "docs/guide.md", "docs/runbooks/a.md", "docs/runbooks/b.md", "src/a.py", "src/b.py",
                "web/x.html"]
        self.assertEqual(sorted(mig.collapse_touches(docs, ("docs/loops", "docs/proposals"))),
                         sorted(["docs/api.md", "docs/guide.md", "docs/runbooks/**", "src/**", "web/**"]))
        self.assertNotIn("docs/**", mig.collapse_touches(["docs/%d/x.md" % i for i in range(8)], ("docs/loops",)))

    def test_yaml_scalar(self):
        self.assertEqual(mig.yaml_scalar("plain words"), "plain words")
        self.assertEqual(mig.yaml_scalar("a: b"), '"a: b"')
        self.assertEqual(mig.yaml_scalar('say "hi"'), '"say \\"hi\\""')
        self.assertEqual(mig.yaml_scalar("owner/repo#3"), '"owner/repo#3"')
        self.assertEqual(mig.yaml_scalar("yes"), '"yes"')
        self.assertEqual(mig.yaml_scalar(12), "12")
        self.assertEqual(mig.yaml_list(["src/x.py", "a, b"]), '[src/x.py, "a, b"]')

    def test_find_prs(self):
        g = mig.Git(tempfile.gettempdir())
        self.assertEqual(mig.find_prs("merged acme/site#1 and #2; deployed via #7, #7 again", g),
                         ["acme/site#1", "acme/site#2", "7"])

    def test_step_refs(self):
        self.assertEqual(mig.step_refs("after Steps 2, 4a, 5 and 7 (per the revision)"), ["2", "4a", "5", "7"])
        self.assertEqual(mig.step_refs("(D5, after Step 4)"), ["4"])
        self.assertEqual(mig.step_refs("needs Steps 1–3"), ["1", "2", "3"])
        self.assertEqual(mig.step_refs("rides in Step 6's build"), [])


if __name__ == "__main__":
    unittest.main()
