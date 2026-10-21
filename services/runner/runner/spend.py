"""What a session spends, always as an estimate (command-center/D21, D23; session-runner C4).

While a session runs, the runner sums each model response's usage at list price. Input and cache tokens are
exact per step; output tokens are a placeholder until the result arrives, so the running figure runs low. At the
end, the figure is the SDK's own estimate (`total_cost_usd`), overshoot included. Before a start, the estimate
for a skill on its model is the median of that pairing's last 10 measured sessions, and none without any.
"""

import statistics
import time

PER_MILLION = 1_000_000


def _tokens(usage):
    usage = usage or {}
    return {
        "input": int(usage.get("input_tokens") or 0),
        "output": int(usage.get("output_tokens") or 0),
        "cache_creation": int(usage.get("cache_creation_input_tokens") or 0),
        "cache_read": int(usage.get("cache_read_input_tokens") or 0),
    }


def cost(usage, prices):
    """The list-price cost of one usage block, in dollars."""
    tokens = _tokens(usage)
    split = (usage or {}).get("cache_creation") or {}
    one_hour = int(split.get("ephemeral_1h_input_tokens") or 0)
    five_minutes = tokens["cache_creation"] - one_hour
    return (tokens["input"] * prices["input"] + tokens["output"] * prices["output"]
            + five_minutes * prices["cache_write_5m"] + one_hour * prices["cache_write_1h"]
            + tokens["cache_read"] * prices["cache_read"]) / PER_MILLION


def spend(basis, usd, tokens, wall_clock_s, as_of, overshoot_usd=None):
    """A Spend object of openapi.yaml. Every figure in it is an estimate, and it says so."""
    return {"kind": "estimate", "basis": basis, "usd": round(max(usd, 0.0), 6),
            "overshoot_usd": None if overshoot_usd is None else round(max(overshoot_usd, 0.0), 6),
            "tokens": tokens, "wall_clock_s": round(max(wall_clock_s, 0.0), 1), "as_of": as_of}


class Meter:
    """Sums a running session's per-step usage. Several messages can share one model response (parallel tool
    use); they carry the same message id and usage, so each response counts once."""

    def __init__(self, prices, budget_usd, monotonic=time.monotonic):
        self.prices, self.budget_usd, self.monotonic = prices, budget_usd, monotonic
        self.started = monotonic()
        self._responses = {}

    def add(self, message_id, usage):
        if usage:
            self._responses[message_id or f"anonymous-{len(self._responses)}"] = usage

    @property
    def usd(self):
        return sum(cost(u, self.prices) for u in self._responses.values())

    @property
    def tokens(self):
        total = {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0}
        for usage in self._responses.values():
            for key, value in _tokens(usage).items():
                total[key] += value
        return total

    @property
    def crossed(self):
        """Whether the responses so far have taken the session past its budget (D21: it may pass it by one)."""
        return self.usd > self.budget_usd

    def elapsed(self):
        return self.monotonic() - self.started

    def snapshot(self, as_of):
        return spend("per-step usage", self.usd, self.tokens, self.elapsed(), as_of)

    def final(self, as_of, total_cost_usd=None, usage=None):
        """The session's final estimate: the SDK's when it gave one, the running sum otherwise."""
        if total_cost_usd is None:
            usd, tokens, basis = self.usd, self.tokens, "per-step usage"
        else:
            usd, tokens, basis = float(total_cost_usd), _tokens(usage) if usage else self.tokens, "sdk result"
        return spend(basis, usd, tokens, self.elapsed(), as_of, overshoot_usd=usd - self.budget_usd)


def estimate_from(measurements):
    """The Estimate object of openapi.yaml for a pairing's measured sessions, newest first, or None."""
    recent = list(measurements)[:10]
    if not recent:
        return None
    return {"kind": "estimate", "usd": round(statistics.median(m["usd"] for m in recent), 6),
            "wall_clock_s": round(statistics.median(m["wall_clock_s"] for m in recent), 1), "sessions": len(recent)}
