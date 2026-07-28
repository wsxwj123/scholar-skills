#!/usr/bin/env python3
"""Schema-filtered loader for reviewer-response atomic units.

Why this exists: reviewer-response and revise-sci can share a project dir. A blanket
`units/*.json` glob would slurp revise-sci's flat `NNN_<comment_id>.json` files (which
carry `comment_id` but no `unit_id`) and try to parse them as reviewer-response units,
producing false gate failures or crashes. This helper forward-filters every json by the
reviewer-response unit marker field `unit_id` (required top-level key per
references/atomic-unit-schema.json); anything else is skipped with a stderr warning.
Fail-open on this skill's own units, skip-and-warn on foreign/unreadable files —
never silently drop a legitimate unit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterator


def iter_units(units_dir: Path | str) -> Iterator[tuple[Path, dict]]:
    """Yield (path, unit_dict) for JSON files that are reviewer-response units.

    Skips (with a stderr warning, not an exception):
      - unreadable / malformed JSON;
      - valid JSON lacking the `unit_id` marker (e.g. revise-sci flat comment files).
    """
    units_dir = Path(units_dir)
    for p in sorted(units_dir.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(f"[unit_glob] skip unreadable json {p.name}: {exc}\n")
            continue
        if not isinstance(data, dict) or "unit_id" not in data:
            sys.stderr.write(
                f"[unit_glob] skip non-unit json {p.name} "
                f"(no 'unit_id'; not a reviewer-response unit)\n"
            )
            continue
        yield p, data


def load_units(units_dir: Path | str) -> list[dict]:
    """Return the list of reviewer-response unit dicts under units_dir (filtered)."""
    return [unit for _, unit in iter_units(units_dir)]
