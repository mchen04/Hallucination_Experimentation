#!/usr/bin/env bash
# Ralph loop: re-feeds PROMPT.md to a fresh Claude Code session over and over.
#
# Each iteration runs the eval, analyzes failures, mutates strategy/techniques,
# and commits + pushes. See PROMPT.md for the per-iteration instructions.
#
# Usage:
#   ./ralph_loop.sh                # forever
#   ./ralph_loop.sh --iters 5      # bounded
#   ./ralph_loop.sh --once         # one iteration (debug)
set -uo pipefail

cd "$(dirname "$0")"

MAX_ITERS=${MAX_ITERS:-0}   # 0 means forever
case "${1:-}" in
  --once)  MAX_ITERS=1 ;;
  --iters) MAX_ITERS="${2:-0}" ;;
  "")      ;;
  *)       echo "unknown arg: $1" >&2; exit 2 ;;
esac

LOCK=".ralph_lock"
if [[ -e "$LOCK" ]]; then
  echo "another ralph loop is running (lock: $LOCK). exit." >&2
  exit 1
fi
trap 'rm -f "$LOCK"' EXIT
touch "$LOCK"

mkdir -p experiments results
: > experiments/loop.log  # truncate runtime log each launch

i=0
while :; do
  i=$((i + 1))
  if [[ "$MAX_ITERS" -gt 0 && "$i" -gt "$MAX_ITERS" ]]; then
    echo "[loop] reached MAX_ITERS=$MAX_ITERS, stopping."
    break
  fi

  echo "============================================================"
  echo "[loop] iteration $i  $(date -u +%FT%TZ)"
  echo "============================================================"

  # Re-feed PROMPT.md into a fresh Claude Code session.
  # --dangerously-skip-permissions: required for unattended forever-loop.
  # We deliberately do NOT set a token budget — let each iteration finish.
  claude -p \
    --dangerously-skip-permissions \
    --append-system-prompt "$(cat PROMPT.md)" \
    "Run one iteration of the loop per PROMPT.md. When done, exit normally." \
    2>&1 | tee -a experiments/loop.log

  rc=${PIPESTATUS[0]}
  if [[ $rc -ne 0 ]]; then
    echo "[loop] iteration $i exited rc=$rc. sleeping 30s then continuing." | tee -a experiments/loop.log
    sleep 30
  fi

  # Light backoff between iterations so we don't hammer claude-code's quota.
  sleep 5
done
