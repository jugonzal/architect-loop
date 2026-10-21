"""The runner's config: the defaults the decisions set, and the limits D23 puts on it."""

import unittest

from runner.config import (ALLOWED_TOOLS, CONCERN_TRAILER_SKILLS, DEFAULT_SKILL_MODELS, HOLDING_SKILLS, SCOPES, SKILLS,
                           Config)


class ConfigTest(unittest.TestCase):
    def test_defaults_follow_the_decisions(self):
        config = Config()
        self.assertEqual(config.project, "jugonzal/architect-loop")  # D18
        self.assertEqual(config.cap_per_sponsor, 3)  # D22
        self.assertEqual(config.skill_models["loop-status"], "claude-sonnet-5-5")  # D5
        for skill in ("loop-design", "loop-build", "loop-prove", "loop-ship"):
            self.assertEqual(config.skill_models[skill], "claude-opus-5-5")
        self.assertLessEqual(config.spend_interval_s, 10)  # D23
        self.assertEqual(config.region, "us-east1")  # D32
        self.assertEqual(ALLOWED_TOOLS, ("Bash", "Read", "Write", "Edit", "Glob", "Grep", "Skill"))  # D3
        self.assertEqual(config.budget_ceiling_usd, 10.0)  # D8
        self.assertEqual(HOLDING_SKILLS, ("loop-build", "loop-design"))  # D6
        self.assertEqual(CONCERN_TRAILER_SKILLS, ("loop-build",))  # command-center/D45

    def test_each_skill_is_dispatched_on_what_runner_dispatch_c3_lists(self):
        self.assertEqual(SCOPES, {"concern": ("loop-design", "loop-build", "loop-prove", "loop-status"),
                                  "loop": ("loop-design", "loop-status"),
                                  "environment": ("loop-ship",)})
        self.assertEqual({s for skills in SCOPES.values() for s in skills}, set(SKILLS))
        self.assertTrue(set(HOLDING_SKILLS) <= set(SCOPES["concern"]))

    def test_a_ceiling_that_is_not_a_positive_amount_is_refused(self):
        for ceiling in (0, -1, float("inf"), float("nan")):
            with self.subTest(ceiling=ceiling), self.assertRaises(ValueError):
                Config(budget_ceiling_usd=ceiling)

    def test_publishing_less_often_than_every_ten_seconds_is_refused(self):
        with self.assertRaises(ValueError):
            Config(spend_interval_s=10.5)
        with self.assertRaises(ValueError):
            Config(spend_interval_s=0)
        self.assertEqual(Config(spend_interval_s=10).spend_interval_s, 10)

    def test_every_skill_needs_a_model_with_a_price(self):
        with self.assertRaises(ValueError):
            Config(skill_models={"loop-build": "claude-opus-5-5"})
        with self.assertRaises(ValueError):
            Config(skill_models={**DEFAULT_SKILL_MODELS, "loop-build": "claude-unpriced-1"})

    def test_a_cap_below_one_is_refused(self):
        with self.assertRaises(ValueError):
            Config(cap_per_sponsor=0)

    def test_it_reads_the_environment(self):
        config = Config.from_env({
            "RUNNER_CAP_PER_SPONSOR": "1", "RUNNER_SKILL_MODELS": '{"loop-build": "claude-sonnet-5-5"}',
            "RUNNER_SPEND_INTERVAL_S": "2.5", "COMMIT_SHA": "abc1234", "RUNNER_APP_SLUG": "architect-loop-runner",
            "RUNNER_STORE": "/data/runner.sqlite3", "RUNNER_BUDGET_CEILING_USD": "2.5",
        })
        self.assertEqual(config.budget_ceiling_usd, 2.5)
        self.assertEqual(config.cap_per_sponsor, 1)
        self.assertEqual(config.skill_models["loop-build"], "claude-sonnet-5-5")
        self.assertEqual(config.skill_models["loop-status"], "claude-sonnet-5-5")
        self.assertEqual(config.spend_interval_s, 2.5)
        self.assertEqual(config.commit, "abc1234")
        self.assertEqual(config.bot_login, "architect-loop-runner[bot]")
        self.assertEqual(config.store_path, "/data/runner.sqlite3")
        self.assertEqual(set(config.skill_models), set(SKILLS))

    def test_an_empty_environment_gives_the_defaults(self):
        self.assertEqual(Config.from_env({}), Config())


if __name__ == "__main__":
    unittest.main()
