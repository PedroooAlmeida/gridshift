"""Opt-in live extraction eval. Makes paid API calls; never run by offline CI."""
import argparse
import json
import os
from pathlib import Path
from .agent import parse_llm
from .evaluate import ROOT, parser_evals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "evals/llm-local.json")
    args = parser.parse_args()
    if not os.environ.get("OPENAI_API_KEY"):
        parser.error("Set OPENAI_API_KEY in your environment; never commit it")
    result = parser_evals(lambda text: parse_llm(text).model_dump(mode="json"))
    result["mode"] = "live_openai"
    result["model"] = os.environ.get("GRIDSHIFT_MODEL", "gpt-4.1-mini")
    args.output.write_text(json.dumps(result, indent=2))
    print(f"Live extraction exact-field score: {result['passed']}/{result['total']}")
    if result["passed"] != result["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
