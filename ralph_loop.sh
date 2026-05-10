#!/usr/bin/env bash
# Ralph loop: re-feeds PROMPT.md to a fresh Claude Code session each iteration.
#
# Safety features (thermal/quota/runaway guards):
#   - Per-iteration hard timeout       (ITER_TIMEOUT_S, default 1200 = 20 min)
#   - Inter-iteration cooldown         (COOLDOWN_S,     default 60s)
#   - Auto-stop on score stagnation    (STAGNATION_LIMIT, default 8 iters
#                                       with no improvement to results/best.json)
#   - Wall-clock budget                (MAX_HOURS,      default 12)
#   - Iteration budget                 (MAX_ITERS,      default 50, 0=unlimited)
#   - Consecutive-failure circuit      (FAIL_STREAK_LIMIT, default 3)
#   - SIGINT/SIGTERM trap kills child clauded sessions before exiting
#
# Usage:
#   ./ralph_loop.sh                # default safe mode (50 iters, 12h cap, stagnation guard)
#   ./ralph_loop.sh --once         # single iteration (debug)
#   ./ralph_loop.sh --iters 5      # bounded
#   ./ralph_loop.sh --forever      # opt-in unbounded (still has stagnation + thermal guards)
#
# Stop manually:
#   pkill -f ralph_loop.sh   (or Ctrl+C if foreground; trap will clean up children)
set -uo pipefail

cd "$(dirname "$0")"

# ---- knobs (env-overridable) ----
ITER_TIMEOUT_S=${ITER_TIMEOUT_S:-1200}
COOLDOWN_S=${COOLDOWN_S:-60}
STAGNATION_LIMIT=${STAGNATION_LIMIT:-8}
MAX_HOURS=${MAX_HOURS:-12}
MAX_ITERS=${MAX_ITERS:-50}
FAIL_STREAK_LIMIT=${FAIL_STREAK_LIMIT:-3}

case "${1:-}" in
  --once)    MAX_ITERS=1 ;;
  --iters)   MAX_ITERS="${2:-0}" ;;
  --forever) MAX_ITERS=0 ;;
  "")        ;;
  *)         echo "unknown arg: $1" >&2; exit 2 ;;
esac

# ---- lock + cleanup trap ----
LOCK=".ralph_lock"
if [[ -e "$LOCK" ]]; then
  echo "another ralph loop is running (lock: $LOCK). exit." >&2
  exit 1
fi
trap '
  ec=$?
  rm -f "$LOCK"
  # Kill any in-flight orchestrator child started by this loop.
  if [[ -n "${CHILD_PID:-}" ]]; then
    kill "$CHILD_PID" 2>/dev/null || true
    sleep 2
    kill -9 "$CHILD_PID" 2>/dev/null || true
  fi
  echo "[loop] cleanup done, exit=$ec"
' EXIT INT TERM
touch "$LOCK"

mkdir -p experiments results
: > experiments/loop.log

# ---- helpers ----
hash_best() {
  if [[ -f results/best.json ]]; then
    shasum -a 256 results/best.json | cut -d' ' -f1
  else
    echo "none"
  fi
}

START_EPOCH=$(date +%s)
deadline_epoch=$((START_EPOCH + MAX_HOURS * 3600))

last_best=$(hash_best)
stagnation=0
fail_streak=0
i=0

while :; do
  i=$((i + 1))

  # Iteration cap
  if [[ "$MAX_ITERS" -gt 0 && "$i" -gt "$MAX_ITERS" ]]; then
    echo "[loop] reached MAX_ITERS=$MAX_ITERS, stopping." | tee -a experiments/loop.log
    break
  fi

  # Wall-clock cap
  now=$(date +%s)
  if [[ "$now" -ge "$deadline_epoch" ]]; then
    echo "[loop] MAX_HOURS=$MAX_HOURS elapsed (since $(date -r $START_EPOCH)), stopping." | tee -a experiments/loop.log
    break
  fi

  echo "============================================================" | tee -a experiments/loop.log
  echo "[loop] iteration $i  $(date -u +%FT%TZ)  elapsed=$((now - START_EPOCH))s  stagnation=$stagnation/$STAGNATION_LIMIT" | tee -a experiments/loop.log
  echo "============================================================" | tee -a experiments/loop.log

  # Run one orchestrator iteration with a hard timeout so a stuck session
  # cannot run forever. `timeout` forwards SIGTERM then SIGKILL.
  iter_start=$(date +%s)
  set +e
  timeout --kill-after=30 "$ITER_TIMEOUT_S" \
    claude -p \
      --dangerously-skip-permissions \
      --append-system-prompt "$(cat PROMPT.md)" \
      "Run one iteration of the loop per PROMPT.md. When done, exit normally." \
      >>experiments/loop.log 2>&1 &
  CHILD_PID=$!
  wait "$CHILD_PID"
  rc=$?
  CHILD_PID=""
  set -e
  iter_dur=$(( $(date +%s) - iter_start ))

  if [[ $rc -eq 124 ]]; then
    echo "[loop] iter $i hit ITER_TIMEOUT_S=$ITER_TIMEOUT_S, killed." | tee -a experiments/loop.log
    fail_streak=$((fail_streak + 1))
  elif [[ $rc -ne 0 ]]; then
    echo "[loop] iter $i exited rc=$rc (after ${iter_dur}s)" | tee -a experiments/loop.log
    fail_streak=$((fail_streak + 1))
  else
    fail_streak=0
  fi

  # Consecutive-failure circuit breaker
  if [[ "$fail_streak" -ge "$FAIL_STREAK_LIMIT" ]]; then
    echo "[loop] $fail_streak consecutive failures — circuit-breaker tripped, stopping." | tee -a experiments/loop.log
    break
  fi

  # Stagnation detection — best.json unchanged for STAGNATION_LIMIT iters
  cur_best=$(hash_best)
  if [[ "$cur_best" == "$last_best" ]]; then
    stagnation=$((stagnation + 1))
  else
    stagnation=0
    last_best="$cur_best"
  fi
  if [[ "$stagnation" -ge "$STAGNATION_LIMIT" ]]; then
    echo "[loop] no improvement for $stagnation iters — calling it. Stopping." | tee -a experiments/loop.log
    break
  fi

  echo "[loop] iter $i done in ${iter_dur}s. cooling down ${COOLDOWN_S}s..." | tee -a experiments/loop.log
  sleep "$COOLDOWN_S"
done

echo "[loop] finished after $i iterations, $(( $(date +%s) - START_EPOCH ))s elapsed." | tee -a experiments/loop.log
