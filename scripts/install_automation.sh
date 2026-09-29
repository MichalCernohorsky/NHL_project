#!/usr/bin/env bash
# Installs (or removes) the launchd agents that run the daily NHL tool jobs.
#
#   scripts/install_automation.sh              # install or reinstall
#   scripts/install_automation.sh --uninstall  # remove the agents, keep the logs
#   scripts/install_automation.sh --status     # only show what is loaded
#
# Every plist in automation/ is copied into ~/Library/LaunchAgents with the
# __REPO_ROOT__ placeholder replaced by this repository's absolute path, then
# validated with plutil and loaded with launchctl. Re-running is safe: each
# agent is booted out before it is loaded again.
#
# Written for bash 3.2 (the version Apple ships as /bin/bash).
# User facing output is Czech on purpose.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLIST_SRC_DIR="$REPO_ROOT/automation"
AGENTS_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$REPO_ROOT/logs"
UID_NUM="$(id -u)"
DOMAIN="gui/$UID_NUM"

die() { echo "CHYBA: $*" >&2; exit 1; }
info() { echo "$*"; }

usage() {
    cat <<'USAGE'
Instalace automatiky (launchd) pro NHL tool.

  scripts/install_automation.sh              nainstaluje nebo preinstaluje ulohy
  scripts/install_automation.sh --uninstall  odstrani ulohy (logy zustanou)
  scripts/install_automation.sh --status     jen vypise stav
  scripts/install_automation.sh --help       tato napoveda

Naplanovane ulohy (mistni cas Macu):
  12:30  com.nhltool.daily         make daily
  16:00  com.nhltool.odds-morning  make odds-morning
  17:00  com.nhltool.odds-closing  make odds-closing (watcher, bezi do rana)

Podrobny navod: docs/automation.md
USAGE
}

require_macos() {
    if [ "$(uname -s)" != "Darwin" ]; then
        die "tento instalator funguje jen na macOS (launchd). Zjisteny system: $(uname -s)"
    fi
    command -v launchctl >/dev/null 2>&1 || die "launchctl nenalezen."
}

# Absolute repo path -> XML text safe for a <string> value.
xml_escape() {
    printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'
}

# XML escaped path -> safe sed replacement text.
sed_escape() {
    printf '%s' "$1" | sed -e 's/[\\&|]/\\&/g'
}

# Number of plist templates in automation/. A plain glob is used everywhere
# instead of `ls`, so that repository paths containing spaces still work.
plist_count() {
    count=0
    for src in "$PLIST_SRC_DIR"/*.plist; do
        [ -f "$src" ] && count=$((count + 1))
    done
    printf '%s' "$count"
}

label_of() {
    basename "$1" .plist
}

# Label -> the job name the wrapper uses for its log file (plist argv[2]).
job_of() {
    printf '%s' "${1#com.nhltool.}"
}

# Newest logs/<job>_<date>.log, or empty when the job has never run. The file
# names end in an ISO date, so alphabetical glob order IS chronological order;
# a plain glob (never `ls`) keeps paths with spaces intact.
last_log_of() {
    latest=""
    for f in "$LOG_DIR/$(job_of "$1")_"*.log; do
        [ -f "$f" ] && latest="$f"
    done
    printf '%s' "$latest"
}

scheduled_time_of() {
    # Reads StartCalendarInterval from an installed plist; "?" when unreadable.
    plist="$1"
    h=$(/usr/libexec/PlistBuddy -c "Print :StartCalendarInterval:Hour" "$plist" 2>/dev/null)
    m=$(/usr/libexec/PlistBuddy -c "Print :StartCalendarInterval:Minute" "$plist" 2>/dev/null)
    if [ -n "$h" ] && [ -n "$m" ]; then
        printf '%02d:%02d' "$h" "$m"
    else
        printf '%s' "?"
    fi
}

unload_agent() {
    label="$1"
    plist="$2"
    launchctl bootout "$DOMAIN/$label" >/dev/null 2>&1 \
        || launchctl unload "$plist" >/dev/null 2>&1 \
        || true
}

load_agent() {
    label="$1"
    plist="$2"
    # A previous `launchctl unload -w` could have left the service disabled.
    launchctl enable "$DOMAIN/$label" >/dev/null 2>&1 || true
    attempt=1
    while [ "$attempt" -le 3 ]; do
        if launchctl bootstrap "$DOMAIN" "$plist" >/dev/null 2>&1; then
            return 0
        fi
        # launchd may still be tearing the old instance down.
        sleep 1
        attempt=$((attempt + 1))
    done
    # Older macOS releases (and some edge cases) only understand load.
    launchctl load -w "$plist" >/dev/null 2>&1
}

print_status() {
    info ""
    info "Stav uloh (launchctl list):"
    printf "  %-26s %-10s %-14s %s\n" "ULOHA" "PID" "POSLEDNI_KOD" "PLAN"
    found_any=0
    for src in "$PLIST_SRC_DIR"/*.plist; do
        [ -f "$src" ] || continue
        label=$(label_of "$src")
        dst="$AGENTS_DIR/$label.plist"
        if [ -f "$dst" ]; then
            plan=$(scheduled_time_of "$dst")
        else
            plan="-"
        fi
        line=$(launchctl list 2>/dev/null | awk -v l="$label" '$3 == l { print $1" "$2 }')
        if [ -n "$line" ]; then
            found_any=1
            pid=$(printf '%s' "$line" | awk '{print $1}')
            rc=$(printf '%s' "$line" | awk '{print $2}')
            [ "$pid" = "-" ] && pid="nebezi"
            printf "  %-26s %-10s %-14s %s\n" "$label" "$pid" "$rc" "$plan"
        else
            printf "  %-26s %-10s %-14s %s\n" "$label" "nenactena" "-" "$plan"
        fi
    done
    if [ "$found_any" -eq 0 ]; then
        info ""
        info "  Zadna uloha neni nactena. Spust: scripts/install_automation.sh"
    fi
    info ""
    info "  PID = bezi prave ted (watcher bezi i nekolik hodin)."
    info "  POSLEDNI_KOD = navratovy kod posledniho behu. Pozor: launchctl"
    info "  hlasi 0 i u ulohy, ktera jeste NIKDY nebezela - samotna nula tedy"
    info "  nedokazuje, ze se neco stalo. Doklad je az log nize."
    info ""
    info "Posledni dokonceny beh podle logu v $LOG_DIR:"
    for src in "$PLIST_SRC_DIR"/*.plist; do
        [ -f "$src" ] || continue
        label=$(label_of "$src")
        log=$(last_log_of "$label")
        if [ -z "$log" ]; then
            printf "  %-26s %s\n" "$label" "zadny log - uloha jeste nikdy nebezela"
            continue
        fi
        last_line=$(grep "KONEC uloha" "$log" 2>/dev/null | tail -1)
        if [ -z "$last_line" ]; then
            last_line="beh zacal, ale neskoncil (bezi prave ted, nebo byl prerusen)"
        fi
        printf "  %-26s %s\n" "$label" "$(basename "$log"): $last_line"
    done
}

do_install() {
    require_macos
    [ -d "$PLIST_SRC_DIR" ] || die "slozka $PLIST_SRC_DIR neexistuje."
    case "$REPO_ROOT" in
        *"|"*) die "cesta k repozitari obsahuje znak '|', to instalator nezvladne: $REPO_ROOT" ;;
    esac

    [ "$(plist_count)" -gt 0 ] || die "v $PLIST_SRC_DIR nejsou zadne .plist soubory."

    mkdir -p "$AGENTS_DIR" || die "nelze vytvorit $AGENTS_DIR"
    mkdir -p "$LOG_DIR" || die "nelze vytvorit $LOG_DIR"

    wrapper="$REPO_ROOT/scripts/daily_wrapper.sh"
    [ -f "$wrapper" ] || die "chybi $wrapper"
    if [ ! -x "$wrapper" ]; then
        info "Doplnuji pravo ke spusteni: $wrapper"
        chmod +x "$wrapper" || die "nelze nastavit prava na $wrapper"
    fi

    info "Repozitar: $REPO_ROOT"
    info "Agenti:    $AGENTS_DIR"
    info "Logy:      $LOG_DIR"
    info ""

    if [ ! -f "$REPO_ROOT/.venv/bin/activate" ]; then
        info "UPOZORNENI: $REPO_ROOT/.venv neexistuje."
        info "            Ulohy pobezi na systemovem pythonu a pravdepodobne selzou."
        info "            Vytvor ho: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
        info ""
    fi
    if ! command -v make >/dev/null 2>&1; then
        info "UPOZORNENI: prikaz 'make' nenalezen. Nainstaluj Command Line Tools:"
        info "            xcode-select --install"
        info ""
    fi

    escaped=$(xml_escape "$REPO_ROOT")
    repl=$(sed_escape "$escaped")

    for src in "$PLIST_SRC_DIR"/*.plist; do
        [ -f "$src" ] || continue
        label=$(label_of "$src")
        dst="$AGENTS_DIR/$label.plist"
        tmp="$dst.tmp.$$"

        sed "s|__REPO_ROOT__|$repl|g" "$src" > "$tmp" || {
            rm -f "$tmp"
            die "nepodarilo se zapsat $tmp"
        }
        if grep -q "__REPO_ROOT__" "$tmp"; then
            rm -f "$tmp"
            die "v $label zustal nenahrazeny zastupny symbol __REPO_ROOT__"
        fi
        if command -v plutil >/dev/null 2>&1; then
            plutil -lint "$tmp" >/dev/null 2>&1 || {
                rm -f "$tmp"
                die "$label.plist neni platny plist (plutil -lint selhal)"
            }
        fi
        mv "$tmp" "$dst" || {
            rm -f "$tmp"
            die "nepodarilo se zapsat $dst"
        }

        unload_agent "$label" "$dst"
        if load_agent "$label" "$dst"; then
            info "  nainstalovano: $label  (plan $(scheduled_time_of "$dst"))"
        else
            info "  POZOR: $label se nepodarilo nacist. Zkus rucne:"
            info "         launchctl bootstrap $DOMAIN \"$dst\""
        fi
    done

    print_status
    info ""
    info "Hotovo. Ulohy se spousti samy podle mistniho casu Macu."
    info "Rucni spusteni ted hned:  launchctl kickstart -k $DOMAIN/com.nhltool.daily"
    info "Navod a omezeni:          docs/automation.md"
}

do_uninstall() {
    require_macos
    [ "$(plist_count)" -gt 0 ] || die "v $PLIST_SRC_DIR nejsou zadne .plist soubory."
    removed=0
    for src in "$PLIST_SRC_DIR"/*.plist; do
        [ -f "$src" ] || continue
        label=$(label_of "$src")
        dst="$AGENTS_DIR/$label.plist"
        unload_agent "$label" "$dst"
        if [ -f "$dst" ]; then
            rm -f "$dst" && info "  odstraneno: $label"
            removed=$((removed + 1))
        else
            info "  nebylo nainstalovano: $label"
        fi
    done
    info ""
    info "Odinstalovano uloh: $removed"
    info "Logy zustavaji v $LOG_DIR (smaz je rucne, pokud je nechces)."
    info "Denni beh ted musis spoustet rucne: make daily, make odds-morning, make odds-closing"
}

ACTION="install"
if [ $# -gt 0 ]; then
    case "$1" in
        --uninstall) ACTION="uninstall" ;;
        --status) ACTION="status" ;;
        --help|-h) usage; exit 0 ;;
        *) usage; die "neznamy parametr: $1" ;;
    esac
fi

case "$ACTION" in
    install) do_install ;;
    uninstall) do_uninstall ;;
    status) require_macos; print_status ;;
esac
