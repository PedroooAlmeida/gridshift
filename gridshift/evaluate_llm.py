"""Opt-in live extraction eval. Makes paid API calls; never run by offline CI."""
import argparse
import json
import os
from pathlib import Path
from .agent import parse_llm, parse_anthropic
from .evaluate import parser_evals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path.cwd() / "evals/llm-local.json")
    parser.add_argument("--provider", choices=["anthropic", "openai"], default="anthropic")
    args = parser.parse_args()
    key_name = "ANTHROPIC_API_KEY" if args.provider == "anthropic" else "OPENAI_API_KEY"
    if not os.environ.get(key_name):
        parser.error(f"Set {key_name} in your environment; never commit it")
    extract = parse_anthropic if args.provider == "anthropic" else parse_llm
    result = parser_evals(lambda text: extract(text).model_dump(mode="json"), dataset="language_events.json")
    result["mode"] = "live_" + args.provider
    result["model"] = (os.environ.get("GRIDSHIFT_ANTHROPIC_MODEL", "claude-sonnet-4-6")
                       if args.provider == "anthropic" else os.environ.get("GRIDSHIFT_MODEL", "gpt-4.1-mini"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2))
    print(f"Live extraction exact-field score: {result['passed']}/{result['total']}")
    if result["passed"] != result["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
