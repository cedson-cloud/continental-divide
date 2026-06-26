"""Step 2 demo: parse each example request and run it through the deterministic rules.

Usage (from backend/, with deps installed):
    python run_examples.py
"""

from __future__ import annotations

import json
from pathlib import Path

from app.models import EventDefinition
from app.rules import evaluate

EXAMPLES_DIR = Path(__file__).parent / "examples"


def main() -> None:
    for path in sorted(EXAMPLES_DIR.glob("*.json")):
        raw = json.loads(path.read_text())
        print(f"\n=== {path.name} ===")
        try:
            event = EventDefinition.model_validate(raw)
        except Exception as exc:  # parse failure is itself a rejection
            print(f"  name: {raw.get('name')!r}")
            print(f"  decision: rejected (schema parse failed)")
            print(f"  errors: {exc}")
            continue

        result = evaluate(event)
        print(f"  name: {event.name!r}  category: {event.category!r}")
        print(f"  properties: {[p.name for p in event.properties]}")
        print(f"  decision: {result.decision.value}")
        print(f"  routed_to_approval: {result.routed_to_approval}")
        for v in result.violations:
            print(f"  violation [{v.rule}]: {v.message}")
        for f in result.flags:
            print(f"  flag: {f}")


if __name__ == "__main__":
    main()
