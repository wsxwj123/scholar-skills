#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_full_package import render_html
from unit_glob import load_units


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Render final hierarchical HTML from atomic JSON units")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output-html", required=True)
    parser.add_argument("--title", default="Reviewer Response Full Package")
    args = parser.parse_args()

    root = Path(args.project_root)
    index_data = read_json(root / "index.json")
    units_dir = root / "units"

    units = load_units(units_dir)

    html = render_html(project_title=args.title, index_data=index_data, units=units)
    out = Path(args.output_html)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"WROTE html: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
