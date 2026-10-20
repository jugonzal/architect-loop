"""Run one Agent SDK session for the session-runner Q1 spike, and record what it reports.

Writes <out>/<label>.jsonl (every message) and <out>/<label>.json (the summary).
"""
import argparse
import asyncio
import dataclasses
import json
import time
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, SystemMessage, query


def to_jsonable(message):
    if dataclasses.is_dataclass(message):
        data = dataclasses.asdict(message)
    else:
        data = {"repr": repr(message)}
    data["_type"] = type(message).__name__
    return data


async def run(args):
    options = ClaudeAgentOptions(
        cwd=args.cwd,
        model=args.model,
        max_budget_usd=args.budget,
        max_turns=args.max_turns,
        permission_mode="dontAsk",
        allowed_tools=args.allow,
        # No user, project or local settings: the only skills are the installed plugin's.
        setting_sources=[],
        plugins=[{"type": "local", "path": args.plugin}],
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    summary = {"label": args.label, "budget_usd": args.budget, "model": args.model, "prompt": args.prompt}
    started = time.monotonic()
    with open(out / f"{args.label}.jsonl", "w") as log:
        try:
            async for message in query(prompt=args.prompt, options=options):
                log.write(json.dumps(to_jsonable(message), default=str) + "\n")
                if isinstance(message, SystemMessage) and message.subtype == "init":
                    summary["init"] = message.data
                if isinstance(message, ResultMessage):
                    summary["result"] = {
                        field: getattr(message, field, None)
                        for field in (
                            "subtype", "is_error", "total_cost_usd", "usage", "model_usage", "num_turns",
                            "duration_ms", "duration_api_ms", "terminal_reason", "result",
                        )
                    }
        except Exception as error:  # A single-shot query raises after yielding an error result.
            summary["raised"] = f"{type(error).__name__}: {error}"
    summary["wall_clock_s"] = round(time.monotonic() - started, 1)
    (out / f"{args.label}.json").write_text(json.dumps(summary, indent=2, default=str))
    result = summary.get("result") or {}
    print(json.dumps({k: result.get(k) for k in ("subtype", "total_cost_usd", "num_turns")} | {
        "label": args.label, "wall_clock_s": summary["wall_clock_s"], "raised": summary.get("raised")}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--cwd", default="/work")
    parser.add_argument("--plugin", default="/plugin")
    parser.add_argument("--out", default="/out")
    parser.add_argument("--model", default="claude-opus-5-5")
    parser.add_argument("--budget", type=float, required=True)
    parser.add_argument("--max-turns", type=int, default=60)
    parser.add_argument("--allow", nargs="*", default=[])
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
