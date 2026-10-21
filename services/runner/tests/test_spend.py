"""C4 and command-center/D21, D23, in parts: how spend is estimated, and the estimate before a start."""

import unittest

from runner.config import DEFAULT_PRICES
from runner.spend import Meter, cost, estimate_from

OPUS = DEFAULT_PRICES["claude-opus-5-5"]
SONNET = DEFAULT_PRICES["claude-sonnet-5-5"]
M = 1_000_000


class Ticks:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class CostTest(unittest.TestCase):
    def test_each_kind_of_token_is_priced_at_its_list_price(self):
        self.assertAlmostEqual(cost({"input_tokens": M}, OPUS), 4.00)
        self.assertAlmostEqual(cost({"output_tokens": M}, OPUS), 20.00)
        self.assertAlmostEqual(cost({"cache_read_input_tokens": M}, OPUS), 0.20)
        self.assertAlmostEqual(cost({"cache_creation_input_tokens": M}, OPUS), 5.00)
        self.assertAlmostEqual(cost({"input_tokens": M, "output_tokens": M}, SONNET), 12.00)

    def test_one_hour_cache_writes_cost_twice_the_input_price(self):
        usage = {"cache_creation_input_tokens": M, "cache_creation": {"ephemeral_1h_input_tokens": M}}
        self.assertAlmostEqual(cost(usage, OPUS), 8.00)

    def test_missing_usage_costs_nothing(self):
        self.assertEqual(cost(None, OPUS), 0)
        self.assertEqual(cost({}, OPUS), 0)


class MeterTest(unittest.TestCase):
    def setUp(self):
        self.ticks = Ticks()
        self.meter = Meter(OPUS, budget_usd=0.10, monotonic=self.ticks)

    def test_each_model_response_counts_once_even_when_several_messages_carry_it(self):
        usage = {"input_tokens": 10_000, "output_tokens": 100}
        self.meter.add("msg_1", usage)
        self.meter.add("msg_1", usage)  # parallel tool use: same response, same usage
        self.meter.add("msg_2", usage)
        self.assertAlmostEqual(self.meter.usd, 2 * (10_000 * 4 + 100 * 20) / M)
        self.assertEqual(self.meter.tokens, {"input": 20_000, "output": 200, "cache_creation": 0, "cache_read": 0})

    def test_the_budget_is_crossed_only_when_passed(self):
        self.meter.add("a", {"input_tokens": 25_000})  # exactly $0.10
        self.assertFalse(self.meter.crossed)
        self.meter.add("b", {"input_tokens": 1})
        self.assertTrue(self.meter.crossed)

    def test_a_running_snapshot_is_labelled_an_estimate_with_no_overshoot_yet(self):
        self.meter.add("a", {"input_tokens": 1000})
        self.ticks.t += 12.34
        snap = self.meter.snapshot("2026-10-20T12:00:00Z")
        self.assertEqual((snap["kind"], snap["basis"], snap["overshoot_usd"]), ("estimate", "per-step usage", None))
        self.assertEqual(snap["wall_clock_s"], 12.3)
        self.assertAlmostEqual(snap["usd"], 0.004)

    def test_the_final_estimate_is_the_sdks_with_the_overshoot(self):
        self.meter.add("a", {"input_tokens": 1000})
        self.ticks.t += 75
        usage = {"input_tokens": 5, "output_tokens": 900, "cache_creation_input_tokens": 20_000,
                 "cache_read_input_tokens": 40_000}
        final = self.meter.final("2026-10-20T12:01:15Z", total_cost_usd=0.1118, usage=usage)
        self.assertEqual((final["kind"], final["basis"]), ("estimate", "sdk result"))
        self.assertAlmostEqual(final["usd"], 0.1118)
        self.assertAlmostEqual(final["overshoot_usd"], 0.0118)
        self.assertEqual(final["tokens"], {"input": 5, "output": 900, "cache_creation": 20_000, "cache_read": 40_000})
        self.assertEqual(final["wall_clock_s"], 75.0)

    def test_a_final_under_budget_has_zero_overshoot(self):
        self.assertEqual(self.meter.final("t", total_cost_usd=0.05)["overshoot_usd"], 0.0)

    def test_without_the_sdks_result_the_final_is_the_running_sum_and_says_so(self):
        self.meter.add("a", {"input_tokens": 50_000})
        final = self.meter.final("t")
        self.assertEqual(final["basis"], "per-step usage")
        self.assertAlmostEqual(final["usd"], 0.2)
        self.assertAlmostEqual(final["overshoot_usd"], 0.1)


class EstimateTest(unittest.TestCase):
    def test_no_measured_session_means_no_estimate(self):
        self.assertIsNone(estimate_from([]))

    def test_the_estimate_is_the_median_of_the_last_ten(self):
        newest_first = [{"usd": u, "wall_clock_s": w} for u, w in
                        [(1.0, 10), (0.2, 20), (0.3, 30), (0.4, 40), (0.5, 50), (0.6, 60), (0.7, 70), (0.8, 80),
                         (0.9, 90), (0.1, 100), (50.0, 5000), (60.0, 6000)]]
        estimate = estimate_from(newest_first)
        self.assertEqual(estimate, {"kind": "estimate", "usd": 0.55, "wall_clock_s": 55.0, "sessions": 10})

    def test_one_measurement_is_its_own_median(self):
        self.assertEqual(estimate_from([{"usd": 0.44, "wall_clock_s": 75.0}]),
                         {"kind": "estimate", "usd": 0.44, "wall_clock_s": 75.0, "sessions": 1})


if __name__ == "__main__":
    unittest.main()
