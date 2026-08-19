#!/usr/bin/env python3
"""
nb_strip.py -- remove stored outputs and execution counts from Jupyter
notebooks, which are usually the largest removable chunk of an agent's
context bill.

Usage:
    python3 tools/nb_strip.py PATH [--inplace] [--suffix .stripped.ipynb]

    PATH        a .ipynb file, or a directory to walk
    --inplace   overwrite the notebooks (default: write alongside)
    --suffix    output suffix when not in place

Prints a before/after byte count per file and a total. Exits 0 always; this is
a cleanup tool, not a gate.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

SKIP_DIRS = {".git", "__pycache__", ".ipynb_checkpoints", "node_modules", ".venv"}


def strip_notebook(nb: dict) -> dict:
    for cell in nb.get("cells", []):
        if cell.get("cell_type") == "code":
            cell["outputs"] = []
            cell["execution_count"] = None
        # widget/scrolled state can also be large
        meta = cell.get("metadata", {})
        for key in ("execution", "scrolled", "collapsed", "outputId", "colab"):
            meta.pop(key, None)
    nbmeta = nb.get("metadata", {})
    nbmeta.pop("widgets", None)
    return nb


def find_notebooks(path: str) -> list[str]:
    if os.path.isfile(path):
        return [path] if path.endswith(".ipynb") else []
    out = []
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(".ipynb"):
                out.append(os.path.join(dirpath, name))
    return sorted(out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Strip Jupyter notebook outputs.")
    p.add_argument("path")
    p.add_argument("--inplace", action="store_true")
    p.add_argument("--suffix", default=".stripped.ipynb")
    args = p.parse_args(argv)

    nbs = find_notebooks(args.path)
    if not nbs:
        print("no notebooks found under %s" % args.path, file=sys.stderr)
        return 0

    before_total = after_total = 0
    for nb_path in nbs:
        before = os.path.getsize(nb_path)
        try:
            with open(nb_path, "r", encoding="utf-8") as fh:
                nb = json.load(fh)
        except Exception as exc:
            print("skip %s (%s)" % (nb_path, exc), file=sys.stderr)
            continue

        nb = strip_notebook(nb)
        out_path = nb_path if args.inplace else nb_path[: -len(".ipynb")] + args.suffix
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(nb, fh, indent=1, ensure_ascii=False)
            fh.write("\n")

        after = os.path.getsize(out_path)
        before_total += before
        after_total += after
        pct = 100.0 * (before - after) / before if before else 0.0
        print("%-52s %8d -> %8d  (-%.0f%%)" % (os.path.basename(nb_path)[:52],
                                               before, after, pct))

    if before_total:
        pct = 100.0 * (before_total - after_total) / before_total
        print("-" * 78)
        print("%-52s %8d -> %8d  (-%.0f%%)" % ("TOTAL", before_total,
                                               after_total, pct))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
