#!/usr/bin/env bash
#
# prep_workspace.sh -- apply the cheap mitigations to a directory before you
# point an agent at it. Audit, strip notebook outputs, quarantine large
# generated artifacts, install AGENTS.md, re-audit.
#
# Usage:
#   tools/prep_workspace.sh /path/to/project              # dry run (default)
#   tools/prep_workspace.sh /path/to/project --apply      # actually do it
#   tools/prep_workspace.sh /path/to/project --apply --budget 200000
#
# Deliberately conservative: it NEVER deletes anything. Large generated files
# are moved into artifacts/, which the installed AGENTS.md declares off-limits.
# Deleting is your call -- see docs/03-mitigations.md M7.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"

TARGET="${1:-}"
shift || true
APPLY=0
BUDGET=200000
THRESHOLD=51200   # bytes; files above this are quarantine candidates

while [ $# -gt 0 ]; do
  case "$1" in
    --apply)      APPLY=1 ;;
    --budget)     BUDGET="$2"; shift ;;
    --threshold)  THRESHOLD="$2"; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ -z "$TARGET" ] || [ ! -d "$TARGET" ]; then
  echo "usage: $0 /path/to/project [--apply] [--budget N] [--threshold BYTES]" >&2
  exit 2
fi

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
run() {
  if [ "$APPLY" -eq 1 ]; then
    eval "$@"
  else
    echo "  would run: $*"
  fi
}

if [ "$APPLY" -eq 0 ]; then
  say "DRY RUN -- nothing will be changed. Re-run with --apply to act."
fi

# ---------------------------------------------------------------- 1. audit --
say "1/5  Auditing $TARGET"
python3 "$HERE/context_audit.py" "$TARGET" --budget "$BUDGET" --top 10 || true

# ------------------------------------------------------- 2. strip notebooks --
say "2/5  Stripping notebook outputs"
if [ "$APPLY" -eq 1 ]; then
  python3 "$HERE/nb_strip.py" "$TARGET" --inplace || echo "  (no notebooks)"
else
  python3 "$HERE/nb_strip.py" "$TARGET" 2>/dev/null \
    | sed 's/^/  /' || echo "  (no notebooks)"
  # remove the .stripped.ipynb probes the dry run just made
  find "$TARGET" -name '*.stripped.ipynb' -delete 2>/dev/null || true
fi

# ---------------------------------------------------- 3. quarantine the fat --
say "3/5  Quarantining files over $((THRESHOLD / 1024))KB into artifacts/"
CANDIDATES=$(find "$TARGET" -maxdepth 1 -type f -size +"$((THRESHOLD / 1024))"k \
             ! -name 'AGENTS.md' ! -name 'STATE.md' ! -name 'README*' \
             2>/dev/null | sort || true)

if [ -z "$CANDIDATES" ]; then
  echo "  nothing over threshold at the top level -- good"
else
  echo "$CANDIDATES" | while read -r f; do
    [ -n "$f" ] || continue
    printf '  %8d  %s\n' "$(wc -c < "$f")" "$(basename "$f")"
  done
  echo
  echo "  These are MOVED, not deleted. Afterwards, review artifacts/ and:"
  echo "    - move back anything you are actively editing this session"
  echo "    - delete what nothing reads at all (docs/03-mitigations.md, M7)"
  echo "  Size is a proxy for 'generated', not for 'unimportant' -- the script"
  echo "  cannot tell your deliverable from a stale build, so check."
  run "mkdir -p '$TARGET/artifacts'"
  echo "$CANDIDATES" | while read -r f; do
    [ -n "$f" ] || continue
    run "mv '$f' '$TARGET/artifacts/'"
  done
fi

# --------------------------------------------------------- 4. install rules --
say "4/5  Installing AGENTS.md"
if [ -f "$TARGET/AGENTS.md" ]; then
  echo "  AGENTS.md already exists -- leaving it alone."
  echo "  Compare against $ROOT/examples/AGENTS.md.sample"
else
  run "cp '$ROOT/examples/AGENTS.md.sample' '$TARGET/AGENTS.md'"
  echo "  Edit it: the directory table needs to match your project."
fi

# ------------------------------------------------------------- 5. re-audit --
say "5/5  Re-auditing (artifacts/ treated as off-limits)"
if [ "$APPLY" -eq 1 ]; then
  python3 "$HERE/context_audit.py" "$TARGET" --budget "$BUDGET" \
          --exclude artifacts --top 10 && STATUS=0 || STATUS=$?
  if [ "${STATUS:-0}" -ne 0 ]; then
    echo
    echo "  Still over budget. Next levers, in order:"
    echo "    - delete superseded versions in artifacts/"
    echo "    - split the task so fewer files are in play at once"
    echo "    - see docs/03-mitigations.md M4 (patch, don't rebuild)"
  fi
else
  echo "  (skipped in dry run)"
fi

say "Done. Now paste prompts/session-start.md as your first message."
