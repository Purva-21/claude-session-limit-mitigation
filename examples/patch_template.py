#!/usr/bin/env python3
"""
patch_template.py -- the alternative to rebuilding a large generated file.

This is a stripped-down version of a patch script that was used in place of
regenerating a 106 KB Jupyter notebook. It exists to make one point concrete:
when an agent must change a large structured file, it should emit a script that
mutates the specific parts, not a new copy of the file.

Why that matters (see docs/03-mitigations.md, M4):

  * the patch is the size of the change, not the size of the file
  * it is re-runnable in a FRESH session after the current one dies
  * a reviewer can see exactly what changed
  * it preserves anything else that touched the file -- metadata, sync-side
    edits -- that a rebuild would silently overwrite

Run:
    python3 patch_template.py in.ipynb out.ipynb
    python3 patch_template.py in.ipynb out.ipynb --dry-run
"""

from __future__ import annotations

import argparse
import ast
import json
import sys

# --------------------------------------------------------------------------
# Stage helpers. Each takes the notebook, mutates it, and reports what it did.
# --------------------------------------------------------------------------


def src(cell) -> str:
    s = cell.get("source", "")
    return s if isinstance(s, str) else "".join(s)


def set_src(cell, text: str) -> None:
    cell["source"] = text


def replace_cell(nb, index: int, new_text: str, log: list) -> None:
    """Stage A: replace one cell wholesale, e.g. to restore truncated prose."""
    cell = nb["cells"][index]
    before = len(src(cell))
    set_src(cell, new_text)
    log.append("cell %d: %d -> %d chars" % (index, before, len(new_text)))


def move_target_last(source: str, target: str) -> tuple[str, bool]:
    """Stage B: reorder top-level defs so `target` is the LAST one.

    Some checkers take the last `return` line in a cell as "the" return
    statement. A private helper defined after the target function therefore
    breaks return-line parity in a way that is invisible if you only read the
    target function. Reordering is an AST-safe fix.
    """
    tree = ast.parse(source)
    lines = source.split("\n")
    spans, order = {}, []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            start = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
            spans[node.name] = (start, node.end_lineno)
            order.append(node.name)

    if not order or target not in spans or order[-1] == target:
        return source, False

    covered = set()
    for name in order:
        a, b = spans[name]
        covered.update(range(a, b))
    preamble = [ln for i, ln in enumerate(lines) if i not in covered]

    new_order = [n for n in order if n != target] + [target]
    blocks = []
    for name in new_order:
        a, b = spans[name]
        blocks.append("\n".join(lines[a:b]).rstrip())

    text = "\n".join(ln for ln in preamble if ln.strip()) or ""
    body = "\n\n\n".join(blocks)
    return ((text + "\n\n\n" + body) if text else body) + "\n", True


def rewrite_text(nb, pattern_fixes: list, skip: set, log: list) -> None:
    """Stage C: targeted string substitutions across markdown cells.

    NOTE the `skip` set. A previous version of this script rewrote structural
    headings ("# Subproblem 1" -> "# Stage 1") and silently broke the required
    document structure. Any blanket text rewrite needs an explicit exemption
    list for cells whose exact text is load-bearing.
    """
    for i, cell in enumerate(nb["cells"]):
        if i in skip or cell.get("cell_type") != "markdown":
            continue
        text = src(cell)
        original = text
        for old, new in pattern_fixes:
            text = text.replace(old, new)
        if text != original:
            set_src(cell, text)
            log.append("cell %d: text rewritten" % i)


# --------------------------------------------------------------------------


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("infile")
    p.add_argument("outfile")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    with open(args.infile, "r", encoding="utf-8") as fh:
        nb = json.load(fh)

    log: list = []

    # ---- configure the stages for your file -------------------------------
    # Cells whose exact text must not be touched (metadata, required headings).
    PROTECTED = {0, 1, 4, 13, 22}

    TEXT_FIXES = [
        # ("old string", "new string"),
    ]

    # Solution cells and the function that must appear last in each.
    TARGETS = {
        # 11: "subproblem_one_fn",
        # 20: "subproblem_two_fn",
        # 29: "main_fn",
    }
    # -----------------------------------------------------------------------

    if TEXT_FIXES:
        rewrite_text(nb, TEXT_FIXES, PROTECTED, log)

    for index, fname in TARGETS.items():
        cell = nb["cells"][index]
        new_src, changed = move_target_last(src(cell), fname)
        if changed:
            set_src(cell, new_src)
            log.append("cell %d: moved %s() to last def" % (index, fname))

    if not log:
        print("no changes -- check your stage configuration", file=sys.stderr)

    for line in log:
        print(line)

    if args.dry_run:
        print("(dry run -- nothing written)")
        return 0

    with open(args.outfile, "w", encoding="utf-8") as fh:
        json.dump(nb, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print("wrote %s" % args.outfile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
