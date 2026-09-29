#!/usr/bin/env bash
# launchd job wrapper for the NHL tool daily pipeline.
#
# Usage:
#   scripts/daily_wrapper.sh <job-label> <command> [args...] [-- <command> [args...]]...
#
# What it does:
#   1. moves into the repository root (derived from this file's own location),
#   2. activates .venv when present (falls back to the system python, loudly),
#   3. runs every step in order, appending stdout AND stderr to
#      logs/<job-label>_<YYYY-MM-DD>.log,
#   4. writes start time, command, exit code and duration of every step,
#   5. fires a macOS notification (osascript) whenever a step exits non-zero.
#
# Steps are separated by a literal "--" argument and run independently: a
# failing step does NOT stop the ones after it, because yesterday's settlement
# must still run when today's odds call fails. The wrapper's own exit code is
# the first non-zero step exit code (0 when everything succeeded).
#
# Written for bash 3.2 (the version Apple ships as /bin/bash) - no associative
# arrays, no mapfile, no ${var,,}.
#
# Log messages are Czech on purpose: the log is read by the user, not by code.

set -uo pipefail

JOB="${1:-}"
if [ -z "$JOB" ] || [ "$JOB" = "--help" ] || [ "$JOB" = "-h" ]; then
    echo "pouziti: daily_wrapper.sh <nazev-ulohy> <prikaz> [args...] [-- <prikaz> [args...]]..." >&2
    echo "priklad: daily_wrapper.sh daily make daily" >&2
    exit 64
fi
shift

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# launchd agents start with a bare PATH; add the usual places a python /
# homebrew install lives so that "make" and "python" resolve.
PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
export PATH

# Python block-buffers stdout when it goes to a file: the closing watcher's
# "waiting until ..." lines would only reach the log when it exits, hours
# later. Unbuffered output makes the log readable while a job runs.
PYTHONUNBUFFERED=1
export PYTHONUNBUFFERED

cd "$REPO_ROOT" || {
    echo "daily_wrapper.sh: nelze prejit do $REPO_ROOT" >&2
    exit 66
}

LOG_DIR="$REPO_ROOT/logs"
mkdir -p "$LOG_DIR" || {
    echo "daily_wrapper.sh: nelze vytvorit $LOG_DIR" >&2
    exit 73
}
LOG_FILE="$LOG_DIR/${JOB}_$(date +%Y-%m-%d).log"

# From here on everything this script and its children print lands in the log.
exec >>"$LOG_FILE" 2>&1

ts() { date "+%Y-%m-%d %H:%M:%S %Z"; }

# macOS notification. Never let a missing/blocked osascript break the job.
notify() {
    title="$1"
    message="$2"
    if command -v osascript >/dev/null 2>&1; then
        # Strip quotes and backslashes: they would break the AppleScript string.
        safe_title=$(printf '%s' "$title" | tr '"\\' "''")
        safe_message=$(printf '%s' "$message" | tr '"\\' "''")
        osascript -e "display notification \"$safe_message\" with title \"$safe_title\"" \
            >/dev/null 2>&1 || echo "[$(ts)] POZNAMKA: notifikaci se nepodarilo zobrazit"
    else
        echo "[$(ts)] POZNAMKA: osascript neni k dispozici, notifikace se neposila"
    fi
}

echo ""
echo "================================================================"
echo "[$(ts)] START uloha='$JOB'"
echo "[$(ts)] repo=$REPO_ROOT  host=$(hostname -s 2>/dev/null || echo '?')  UTC=$(date -u '+%Y-%m-%d %H:%M:%S')"
echo "[$(ts)] log=$LOG_FILE"

if [ -f "$REPO_ROOT/.venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    . "$REPO_ROOT/.venv/bin/activate"
    echo "[$(ts)] venv: $REPO_ROOT/.venv (python: $(command -v python || echo 'NENALEZEN'))"
else
    echo "[$(ts)] UPOZORNENI: $REPO_ROOT/.venv nenalezeno, pouzije se systemovy python"
    notify "NHL tool: uloha '$JOB'" "Chybi .venv v $REPO_ROOT - uloha bezi na systemovem pythonu."
fi

if ! command -v python >/dev/null 2>&1; then
    echo "[$(ts)] UPOZORNENI: prikaz 'python' neni na PATH (PATH=$PATH)."
    echo "[$(ts)]              Kroky, ktere ho potrebuji, skonci s kodem 127."
fi

overall_rc=0
step_no=0
# bash 3.2 (the /bin/bash Apple ships) still treats an EMPTY array as unset
# under `set -u`, so the number of collected arguments is kept in a plain
# scalar instead of asking for ${#cur[@]}.
cur=()
cur_n=0

run_step() {
    if [ "$cur_n" -eq 0 ]; then
        return 0
    fi
    step_no=$((step_no + 1))
    start_epoch=$(date +%s)
    echo ""
    echo "[$(ts)] krok $step_no: ${cur[*]}"
    if ! command -v "${cur[0]}" >/dev/null 2>&1; then
        echo "[$(ts)] krok $step_no: prikaz '${cur[0]}' nenalezen na PATH"
    fi
    "${cur[@]}"
    rc=$?
    end_epoch=$(date +%s)
    echo "[$(ts)] krok $step_no hotov: navratovy kod=$rc, trvani=$((end_epoch - start_epoch))s"
    if [ "$rc" -ne 0 ]; then
        if [ "$overall_rc" -eq 0 ]; then
            overall_rc=$rc
        fi
        notify "NHL tool: uloha '$JOB' selhala" \
               "Krok $step_no (${cur[0]}) skoncil s kodem $rc. Podrobnosti: $LOG_FILE"
    fi
    cur=()
    cur_n=0
    return 0
}

# Same bash 3.2 caveat: "$@" counts as unset under `set -u` when there are no
# positional parameters, so the loop is entered only when there are some.
# Without the guard, `daily_wrapper.sh daily` (a job label and nothing else)
# would die with "unbound variable" instead of the message below.
if [ $# -gt 0 ]; then
    for arg in "$@"; do
        if [ "$arg" = "--" ]; then
            run_step
        else
            cur[$cur_n]="$arg"
            cur_n=$((cur_n + 1))
        fi
    done
fi
run_step

if [ "$step_no" -eq 0 ]; then
    echo "[$(ts)] CHYBA: nebyl zadan zadny prikaz ke spusteni"
    overall_rc=64
fi

echo ""
echo "[$(ts)] KONEC uloha='$JOB' kroku=$step_no celkovy navratovy kod=$overall_rc"
exit "$overall_rc"
