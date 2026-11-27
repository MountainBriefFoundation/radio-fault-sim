"""Run offline examples with ``python -m radio_fault_sim``."""

import argparse
import json

from .scenarios import SCENARIOS, run_scenario


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic in-process TNC/PTT fault scenarios.")
    parser.add_argument("--scenario", choices=("all", *SCENARIOS), default="all")
    parser.add_argument("--json", action="store_true", help="emit structured synthetic observations")
    args = parser.parse_args()
    names = SCENARIOS if args.scenario == "all" else (args.scenario,)
    results = [run_scenario(name) for name in names]
    if args.json:
        print(json.dumps({"model_version": "0.1.0", "scenarios": results}, indent=2, sort_keys=True))
        return
    for result in results:
        print(result["scenario"])
        for sample in result["samples"]:
            print(
                f"  {sample['mono_ms']:4d} ms {sample['label']}: "
                f"queue={sample['queued']} ptt_line={sample['ptt_line']} "
                f"feedback={sample['feedback']} alive={sample['alive']}"
            )
        if result["outcomes"]:
            print(f"  outcomes: {result['outcomes']}")


if __name__ == "__main__":
    main()
