#!/usr/bin/env bash
# ---- Pretty console output (colors + boxes) ---------------------------------
# Enable colors only when stdout is a TTY and NO_COLOR is not set.
COLOR_OK=0
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  COLOR_OK=1
fi

if [ "${COLOR_OK}" -eq 1 ]; then
  BOLD=$'\033[1m'
  DIM=$'\033[2m'
  RED=$'\033[31m'
  GREEN=$'\033[32m'
  YELLOW=$'\033[33m'
  BLUE=$'\033[34m'
  MAGENTA=$'\033[35m'
  CYAN=$'\033[36m'
  RESET=$'\033[0m'
else
  BOLD=""; DIM=""; RED=""; GREEN=""; YELLOW=""; BLUE=""; MAGENTA=""; CYAN=""; RESET=""
fi

# Box horizontal margin (characters removed from full terminal width).
# Can be overridden via environment variable BOX_MARGIN; default 8.
: "${BOX_MARGIN:=8}"

# Draw a rule line with optional title and color (usage: rule "Title" "$BLUE")
rule() {
  local title="${1:-}" ; local color="${2:-}"
  # Prefer COLUMNS if set; fallback to tput; default 80
  local cols="${COLUMNS:-}"
  if ! [[ "$cols" =~ ^[0-9]+$ ]]; then
    cols=$(tput cols 2>/dev/null || echo 80)
  fi
  (( cols < 40 )) && cols=80
  # Leave a small margin to avoid wrapping on some terminals that count ANSI bytes
  local inner=$(( cols - BOX_MARGIN ))
  if (( inner < 10 )); then inner=10; fi
  local line; line=$(printf '%*s' "${inner}" '' | tr ' ' '─')
  if [ -n "${title}" ]; then
    # Compute visible title width without ANSI
    local t=" ${title} "
    local tl=${#t}
    (( tl > inner )) && t=" ${title:0:inner-2} " && tl=${#t}
    local left=$(( (inner - tl) / 2 ))
    local right=$(( inner - left - tl ))
    printf "%s  ─%*s%s%*s─  %s\n" "${color}" "${left}" "" "${t}" "${right}" "" "${RESET}"
  else
    printf "%s  ─%s─  %s\n" "${color}" "${line}" "${RESET}"
  fi
}

# Print a boxed title with optional subtitle (usage: box_title "Main" "small text" "$MAGENTA")
box_title() {
  local title="${1:-}" ; local subtitle="${2:-}" ; local color="${3:-$CYAN}"
  local cols="${COLUMNS:-}"
  if ! [[ "$cols" =~ ^[0-9]+$ ]]; then
    cols=$(tput cols 2>/dev/null || echo 80)
  fi
  (( cols < 40 )) && cols=80
  # Keep a configurable margin on each side to avoid terminal wrap issues
  local w=$(( cols - BOX_MARGIN ))
  (( w < 20 )) && w=20

  local horiz; horiz=$(printf '%*s' "$w" '' | tr ' ' '─')

  # helper: a fully blank line that still shows the vertical borders
  _box_pad() {
    printf "%s  │%*s│  %s\n" "$color" "$w" "" "$RESET"
  }

  # Top border
  printf "%s  ┌%s┐  %s\n" "$color" "$horiz" "$RESET"

  # Padding above title
  _box_pad

  # Title (centered). Apply bold only to title content; keep color active for borders.
  local tl=${#title}
  (( tl > w )) && title="${title:0:w}" && tl=${#title}
  local lp=$(( (w - tl) / 2 ))
  local rp=$(( w - lp - tl ))
  printf "%s  │%*s%s%s%s%*s│  %s\n" \
    "$color" "$lp" "" "$BOLD" "$title" "$RESET$color" "$rp" "" "$RESET"

  # Padding below title
  _box_pad

  # Optional subtitle block with padding
  if [ -n "$subtitle" ]; then
    # padding above subtitle
    _box_pad
    local sl=${#subtitle}
    (( sl > w )) && subtitle="${subtitle:0:w}" && sl=${#subtitle}
    local lp2=$(( (w - sl) / 2 ))
    local rp2=$(( w - lp2 - sl ))
    printf "%s  │%*s%s%*s│  %s\n" "$color" "$lp2" "" "$subtitle" "$rp2" "" "$RESET"
    # padding below subtitle
    _box_pad
  fi

  # Bottom border
  printf "%s  └%s┘  %s\n" "$color" "$horiz" "$RESET"
}

# Print a boxed block with centered lines. Borders are printed on every line, including blank padding.
# Usage: box_center <color> [pad_top] [pad_between] [pad_bottom] -- "Line 1" "" "Line N"
box_center() {
  # Usage: box_center <color> [pad_top] [pad_between] [pad_bottom] -- "Line 1" "" "Line N"
  # pad_* default to 1 if omitted. Borders are printed on every line (also on padding).
  local color="$1"; shift
  local pad_top=1 pad_between=1 pad_bottom=1

  # Parse optional numeric paddings until we hit a literal '--'
  while [[ $# -gt 0 && "$1" != "--" ]]; do
    case "$1" in
      ''|*[!0-9]*) break;;
      *) if (( pad_top == 1 )); then pad_top="$1"
         elif (( pad_between == 1 )); then pad_between="$1"
         else pad_bottom="$1"
         fi
         shift
         ;;
    esac
  done
  # Expect delimiter before the lines
  if [[ "$1" == "--" ]]; then shift; fi

  # Terminal width handling
  local cols="${COLUMNS:-}"
  if ! [[ "$cols" =~ ^[0-9]+$ ]]; then
    cols=$(tput cols 2>/dev/null || echo 80)
  fi
  (( cols < 40 )) && cols=80
  local w=$(( cols - BOX_MARGIN ))
  (( w < 20 )) && w=20

  local horiz; horiz=$(printf '%*s' "$w" '' | tr ' ' '─')

  # helpers
  _pad_line() { printf "%s  │%*s│  %s\n" "$color" "$w" "" "$RESET"; }
  _center_line() {
    # Prints one centered content line with borders, preserving color on borders only.
    local s="$1"
    local sl=${#s}
    if (( sl > w )); then s="${s:0:w}"; sl=${#s}; fi
    local lp=$(( (w - sl) / 2 ))
    local rp=$(( w - lp - sl ))
    # keep color active for borders; reset only for content; re-enable for right border
    printf "%s  │%*s%s%s%s%*s│  %s\n" \
      "$color" "$lp" "" "$RESET" "$s" "$color" "$rp" "" "$RESET"
  }

  # Top border
  printf "%s  ┌%s┐  %s\n" "$color" "$horiz" "$RESET"

  # Top padding (bordered blanks)
  local i
  for ((i=0; i<pad_top; i++)); do _pad_line; done

  # Body with between-padding bordered lines
  local first=1
  while [[ $# -gt 0 ]]; do
    local line="$1"; shift
    _center_line "$line"
    # Between-padding after every line except the last
    if [[ $# -gt 0 ]]; then
      local j
      for ((j=0; j<pad_between; j++)); do _pad_line; done
    fi
  done

  # Bottom padding
  for ((i=0; i<pad_bottom; i++)); do _pad_line; done

  # Bottom border
  printf "%s  └%s┘  %s\n" "$color" "$horiz" "$RESET"
}

status_color() {
  case "$1" in
    OK|ok|0) echo "${GREEN}";;
    FAIL|fail|1|2|3|4|5|6|7|8|9|10) echo "${RED}";;
    *) echo "${YELLOW}";;
  esac
}
# -----------------------------------------------------------------------------
# test_all_strategy.sh
# -----------------------------------------------------------------------------
# Usage:
#   ./test_all_strategy.sh <strategies_dir> [-- <extra args passed to test_strategy.sh>]
#
# What it does:
#   - Recursively scans the provided directory for Python strategy files (*.py)
#   - Extracts strategy class names that subclass IStrategy
#   - Runs ./test_strategy.sh <StrategyClass> for each discovered class
#   - Prints a compact ASCII summary table (strategy, exit code, status)
#
# Notes:
#   - Comments are in English as requested.
#   - No parallelization by default (keeps logs readable). If you want parallel,
#     tell me and I will add a -j flag using xargs -P.
# -----------------------------------------------------------------------------

set -u -o pipefail

# Ensure we are running under bash even if invoked via /bin/sh
if [ -z "${BASH_VERSION:-}" ]; then
  exec bash "$0" "$@"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"
TEST_SCRIPT="${ROOT_DIR}/test_strategy.sh"

usage() {
  cat <<USAGE
Usage: $0 <strategies_dir> [-- <extra args to pass to test_strategy.sh>]

Examples:
  $0 user_data/strategies
  $0 user_data/strategies -- -m summary

USAGE
}

if [[ ${#} -lt 1 ]]; then
  usage
  exit 1
fi


STRAT_DIR="$1"; shift || true
declare -a EXTRA_ARGS
EXTRA_ARGS=("$@")

# Normalize EXTRA_ARGS: drop a leading "--" (separator) if provided by the caller,
# so we don't pass it down to test_strategy.sh as a literal argument.
if ((${#EXTRA_ARGS[@]} > 0)); then
  if [[ "${EXTRA_ARGS[0]}" == "--" ]]; then
    EXTRA_ARGS=("${EXTRA_ARGS[@]:1}")
  fi
fi

if [[ ! -x "${TEST_SCRIPT}" ]]; then
  echo "ERROR: test_strategy.sh not found or not executable at: ${TEST_SCRIPT}" >&2
  exit 2
fi

if [[ ! -d "${STRAT_DIR}" ]]; then
  echo "ERROR: strategies_dir does not exist: ${STRAT_DIR}" >&2
  exit 3
fi

#
# Find Python files recursively (robust for spaces/newlines via -print0; portable for macOS Bash 3.2)
PY_FILES=()
_tmp_py_files="$(mktemp -t ta_pyfiles.XXXXXX)"
# Exclude common virtualenvs and __pycache__ to avoid noise
find "${STRAT_DIR}" \
  -type f -name "*.py" \
  -not -path "*/__pycache__/*" \
  -not -path "*/.venv/*" -not -path "*/venv/*" -not -path "*/env/*" \
  -print0 2>/dev/null > "${_tmp_py_files}"

# Read NUL-delimited results into the array (handles spaces/newlines safely)
while IFS= read -r -d '' _py; do
  PY_FILES+=("${_py}")
done < "${_tmp_py_files}"
rm -f "${_tmp_py_files}"

# Sort the array safely
if [[ ${#PY_FILES[@]} -gt 0 ]]; then
  IFS=$'\n' PY_FILES=($(printf '%s\n' "${PY_FILES[@]}" | sort -u)); unset IFS
fi

if [[ ${#PY_FILES[@]} -eq 0 ]]; then
  echo "No Python files (*.py) found under: ${STRAT_DIR}"
  exit 0
fi

# Extract class names that subclass IStrategy from each file.
# We use grep to pick candidate lines, then sed/awk to extract the class name.
# Pattern handled: class MyStrat(IStrategy):  (allowing spaces and extra bases)
extract_classes() {
  local file="$1"
  # Grep candidate class lines, then cut the class name safely.
  # This tolerates: class Name ( IStrategy ): or class Name(IStrategy, Base)
  # 1) Select lines starting with 'class' (ignoring leading spaces) containing 'IStrategy'
  # 2) Strip leading spaces, take the identifier after 'class '
  # 3) Stop at first '(' or ':'
  grep -E '^[[:space:]]*class[[:space:]]+[A-Za-z_][A-Za-z0-9_]*[[:space:]]*\([^)]*IStrategy[^)]*\)[[:space:]]*:' "$file" \
    | sed -E 's/^[[:space:]]*class[[:space:]]+([A-Za-z_][A-Za-z0-9_]*).*/\1/' \
    | sort -u
}

STRATEGIES=()
for f in "${PY_FILES[@]}"; do
  # Portable alternative to process substitution for macOS default Bash 3.2 and when invoked via /bin/sh
  _tmp_classes="$(mktemp -t ta_classes.XXXXXX)"
  extract_classes "$f" > "${_tmp_classes}"
  while IFS= read -r cls; do
    # Avoid empty values
    [[ -n "$cls" ]] && STRATEGIES+=("$cls")
  done < "${_tmp_classes}"
  rm -f "${_tmp_classes}"
done

# De-duplicate strategies while preserving order (portable for Bash 3.2)
if [[ ${#STRATEGIES[@]} -eq 0 ]]; then
  echo "No strategy classes (subclassing IStrategy) found under: ${STRAT_DIR}"
  exit 0
fi

UNIQ_STRATS=()
_tmp_strats="$(printf "%s\n" "${STRATEGIES[@]}" | awk '!seen[$0]++')"
while IFS= read -r _s; do
  [[ -n "${_s}" ]] && UNIQ_STRATS+=("${_s}")
done <<< "${_tmp_strats}"

# -----------------------------------------------------------------------------
# Interactive selection: list strategies and let user choose all or one
# -----------------------------------------------------------------------------
box_title "Discovered strategies (${#UNIQ_STRATS[@]})" "Scan: ${STRAT_DIR}" "$MAGENTA"
printf "%s\n" "${DIM}Below is the numbered list. Choose 'a' for all or a number to run one.${RESET}"
idx_print=0
for s in "${UNIQ_STRATS[@]}"; do
  idx_print=$((idx_print+1))
  printf "  [%d] %s\n" "$idx_print" "$s"
done

# Prompt for selection
CHOICE=""
while :; do
  printf "\n${BOLD}Select:${RESET} ${CYAN}'a'${RESET} for all, or a number ${BOLD}(1..%d)${RESET} for a single strategy: " ${#UNIQ_STRATS[@]}
  IFS= read -r CHOICE
  # Normalize whitespace
  CHOICE=$(printf '%s' "$CHOICE" | tr -d ' \t')
  if [ -z "$CHOICE" ]; then
    echo "Please enter 'a' or a number."
    continue
  fi

  # All
  if [ "$CHOICE" = "a" ] || [ "$CHOICE" = "A" ]; then
    break
  fi

  # Single number?
  case "$CHOICE" in
    ''|*[!0-9]*)
      echo "Please enter a valid number (1..${#UNIQ_STRATS[@]}) or 'a'."
      continue
      ;;
    0)
      echo "Number must be between 1 and ${#UNIQ_STRATS[@]}"
      continue
      ;;
    *)
      num="$CHOICE"
      if [ "$num" -ge 1 ] && [ "$num" -le ${#UNIQ_STRATS[@]} ]; then
        # Keep only the selected strategy
        SELECTED_STRATS=("${UNIQ_STRATS[$((num-1))]}")
        UNIQ_STRATS=("${SELECTED_STRATS[@]}")
        break
      else
        echo "Number must be between 1 and ${#UNIQ_STRATS[@]}"
        continue
      fi
      ;;
  esac
done

# If 'a' was selected, keep all strategies; recompute TOTAL now
TOTAL=${#UNIQ_STRATS[@]}
box_center "$BLUE" 2 2 2 -- "Test session starting" "Total strategies: ${TOTAL}"
printf "%sWorking directory:%s %s\n" "${DIM}" "${RESET}" "${PWD}"

printf "%sStart time:%s       %s\n" "${DIM}" "${RESET}" "$(date +%Y-%m-%d\ %H:%M:%S)"
# Temp file for collecting all profits across strategies
TMP_ALLPROF="$(mktemp -t ta_allprofits.XXXXXX)"

# Track global min/max of total_profit (%) across all strategies/runs
GLOBAL_MIN=""
GLOBAL_MIN_DESC=""
GLOBAL_MAX=""
GLOBAL_MAX_DESC=""

# Run each strategy
RESULTS=()
IDX=0

start_ts=$(date +%Y-%m-%d\ %H:%M:%S)

for strat in "${UNIQ_STRATS[@]}"; do
  IDX=$((IDX+1))
  box_center "$YELLOW" 1 1 1 -- "[${IDX}/${TOTAL}] Testing strategy" "${strat}"
  # Call test_strategy.sh and forward extra args (robust with set -u even if EXTRA_ARGS is empty)
  _cmd_args=("${strat}")
  if ((${#EXTRA_ARGS[@]})); then
    _cmd_args+=("${EXTRA_ARGS[@]}")
  fi
  # Capture output to a temporary log so we can parse the summary table
  _tmp_runlog="$(mktemp -t ta_runlog.XXXXXX)"
  if "${TEST_SCRIPT}" "${_cmd_args[@]}" | tee "${_tmp_runlog}"; then
    RESULTS+=("${strat}|0|OK")
    printf "%s%s%s\n\n" "${GREEN}${BOLD}" "Status: OK" "${RESET}"
  else
    code=$?
    RESULTS+=("${strat}|${code}|FAIL")
    printf "%s%s (exit ${code})%s\n\n" "${RED}${BOLD}" "Status: FAIL" "${RESET}"
  fi

  # Parse total_profit (%) values from the ASCII summary table produced by test_strategy.sh
  # Append rows to a temp tsv for per-strategy min/max aggregation later.
  while IFS=$'\t' read -r _label _val _timerange; do
    # Append raw row for later per-strategy aggregation
    printf "%s\t%s\t%s\t%s\n" "$strat" "$_label" "$_timerange" "$_val" >> "${TMP_ALLPROF}"
    # Track global min/max immediately
    if [[ -z "${GLOBAL_MIN}" ]] || awk "BEGIN{exit !($_val < ${GLOBAL_MIN})}"; then
      GLOBAL_MIN="${_val}"
      GLOBAL_MIN_DESC="${strat} / ${_label} [${_timerange}]"
    fi
    if [[ -z "${GLOBAL_MAX}" ]] || awk "BEGIN{exit !($_val > ${GLOBAL_MAX})}"; then
      GLOBAL_MAX="${_val}"
      GLOBAL_MAX_DESC="${strat} / ${_label} [${_timerange}]"
    fi
  done < <(awk -F'\|' '
    /^\|/ {
      label=$2; gsub(/^ +| +$/,"",label)
      tr=$3;     gsub(/^ +| +$/,"",tr)
      tp=$4;     gsub(/^ +| +$|%/,"",tp)
      if (tp ~ /^-?[0-9]+(\.[0-9]+)?$/) {
        print label "\t" tp "\t" tr
      }
    }
  ' "${_tmp_runlog}")
  rm -f "${_tmp_runlog}"
done

# Pretty ASCII summary table
# Compute column widths
max_len() { awk '{ if (length($0)>m) m=length($0) } END { print (m?m:0) }'; }

# Prepare rows for width calculation
{
  echo "Strategy"; for r in "${RESULTS[@]}"; do echo "${r%%|*}"; done
} > /tmp/.ta_names.$$ 
name_w=$(cat /tmp/.ta_names.$$ | max_len)
rm -f /tmp/.ta_names.$$

status_hdr="Status"
code_hdr="Exit"

# Limits to sane minimum widths
(( name_w < 8 )) && name_w=8
code_w=${#code_hdr}
status_w=${#status_hdr}

# Print header
line() {
  printf "+-%-*s-+-%-*s-+-%-*s-+\n" "$name_w" "" "$code_w" "" "$status_w" "" | tr ' ' '-'
}

line
printf "| %-*s | %-*s | %-*s |\n" "$name_w" "${BOLD}Strategy${RESET}" "$code_w" "${BOLD}${code_hdr}${RESET}" "$status_w" "${BOLD}${status_hdr}${RESET}"
line
for r in "${RESULTS[@]}"; do
  IFS='|' read -r nm code status <<<"$r"
  sc=$(status_color "$status")
  printf "| %-*s | %-*s | %s%-*s%s |\n" \
    "$name_w" "$nm" \
    "$code_w" "$code" \
    "$sc" "$status_w" "$status" "${RESET}"
done

line

# Compute per-strategy min/max from collected rows (strategy, label, timerange, value)
PER_STRAT_MINMAX=$(awk -F'\t' '
  {
    s=$1; lbl=$2; tr=$3; v=$4+0; desc=lbl " [" tr "]";
    if(!(s in seen)){min[s]=v; mind[s]=desc; max[s]=v; maxd[s]=desc; seen[s]=1}
    if(v<min[s]){min[s]=v; mind[s]=desc}
    if(v>max[s]){max[s]=v; maxd[s]=desc}
  }
  END{
    for(s in seen){
      printf "%s\t%.3f\t%s\t%.3f\t%s\n", s, min[s], mind[s], max[s], maxd[s]
    }
  }
' "${TMP_ALLPROF}")

# Pretty print per-strategy min/max
if [ -n "${PER_STRAT_MINMAX}" ]; then
  box_title "Per-strategy profit range" "Min/Max of total profit (%)" "$CYAN"
  # Build an ASCII table
  # Determine widths
  {
    echo "Strategy"; printf "%s\n" "${PER_STRAT_MINMAX}" | awk -F'\t' '{print $1}'
  } > /tmp/.ta_nm.$$; name_w2=$(cat /tmp/.ta_nm.$$ | max_len); rm -f /tmp/.ta_nm.$$
  (( name_w2 < 8 )) && name_w2=8
  min_hdr="Min %"; min_w=${#min_hdr}
  max_hdr="Max %"; max_w=${#max_hdr}
  md_hdr="Min where"; md_w=8
  xd_hdr="Max where"; xd_w=8
  # compute dynamic widths for descriptions
  {
    printf "%s\n" "${PER_STRAT_MINMAX}" | awk -F'\t' '{print $3}'
  } > /tmp/.ta_mindesc.$$; md_w_calc=$(cat /tmp/.ta_mindesc.$$ | max_len); rm -f /tmp/.ta_mindesc.$$
  {
    printf "%s\n" "${PER_STRAT_MINMAX}" | awk -F'\t' '{print $5}'
  } > /tmp/.ta_maxdesc.$$; xd_w_calc=$(cat /tmp/.ta_maxdesc.$$ | max_len); rm -f /tmp/.ta_maxdesc.$$
  (( md_w_calc > md_w )) && md_w=$md_w_calc
  (( xd_w_calc > xd_w )) && xd_w=$xd_w_calc

  # print header line
  printf "+-%-*s-+-%-*s-+-%-*s-+-%-*s-+-%-*s-+\n" "$name_w2" "" "$min_w" "" "$md_w" "" "$max_w" "" "$xd_w" "" | tr ' ' '-'
  printf "| %-*s | %-*s | %-*s | %-*s | %-*s |\n" \
    "$name_w2" "${BOLD}Strategy${RESET}" \
    "$min_w"  "${BOLD}${min_hdr}${RESET}" \
    "$md_w"   "${BOLD}${md_hdr}${RESET}" \
    "$max_w"  "${BOLD}${max_hdr}${RESET}" \
    "$xd_w"   "${BOLD}${xd_hdr}${RESET}"
  printf "+-%-*s-+-%-*s-+-%-*s-+-%-*s-+-%-*s-+\n" "$name_w2" "" "$min_w" "" "$md_w" "" "$max_w" "" "$xd_w" "" | tr ' ' '-'
  printf "%s\n" "${PER_STRAT_MINMAX}" | while IFS=$'\t' read -r s vmin mindesc vmax maxdesc; do
    printf "| %-*s | %*.3f | %-*s | %*.3f | %-*s |\n" \
      "$name_w2" "$s" \
      "$min_w" "$vmin" \
      "$md_w"  "$mindesc" \
      "$max_w" "$vmax" \
      "$xd_w"  "$maxdesc"
  done
  printf "+-%-*s-+-%-*s-+-%-*s-+-%-*s-+-%-*s-+\n" "$name_w2" "" "$min_w" "" "$md_w" "" "$max_w" "" "$xd_w" "" | tr ' ' '-'
fi

# Define summary file before end timestamp
SUMMARY_FILE="${PWD}/test_all_summary_$(date +%Y%m%d_%H%M%S).txt"
end_ts=$(date +%Y-%m-%d\ %H:%M:%S)

box_title "Run summary" "" "$GREEN"
printf "%sTotal strategies:%s %d\n" "${BOLD}" "${RESET}" "${TOTAL}"
printf "%sStarted at:%s       %s\n" "${BOLD}" "${RESET}" "${start_ts}"
printf "%sFinished at:%s      %s\n" "${BOLD}" "${RESET}" "${end_ts}"
if [[ -n "${GLOBAL_MIN}" ]] && [[ -n "${GLOBAL_MAX}" ]]; then
  printf "%sMin total profit:%s  %s%%  %s\n" "${BOLD}" "${RESET}" "${GLOBAL_MIN}" "${DIM}${GLOBAL_MIN_DESC}${RESET}"
  printf "%sMax total profit:%s  %s%%  %s\n" "${BOLD}" "${RESET}" "${GLOBAL_MAX}" "${DIM}${GLOBAL_MAX_DESC}${RESET}"
else
  printf "%sMin/Max total profit:%s  %s\n" "${BOLD}" "${RESET}" "(no summary values parsed)"
fi


# Save summary section to file
{
  echo "Test session summary generated at ${end_ts}"
  echo ""
  line
  printf "| %-*s | %-*s | %-*s |\n" "$name_w" "Strategy" "$code_w" "$code_hdr" "$status_w" "$status_hdr"
  line
  for r in "${RESULTS[@]}"; do
    IFS='|' read -r nm code status <<<"$r"
    printf "| %-*s | %-*s | %-*s |\n" "$name_w" "$nm" "$code_w" "$code" "$status_w" "$status"
  done
  line
  echo "Total strategies: ${TOTAL}"
  echo "Started at    : ${start_ts}"
  echo "Finished at   : ${end_ts}"
  if [[ -n "${GLOBAL_MIN}" ]] && [[ -n "${GLOBAL_MAX}" ]]; then
    echo "Min total profit : ${GLOBAL_MIN}%  ${GLOBAL_MIN_DESC}"
    echo "Max total profit : ${GLOBAL_MAX}%  ${GLOBAL_MAX_DESC}"
  else
    echo "Min/Max total profit : (no summary values parsed)"
  fi
  echo ""
  echo "Per-strategy min/max (total profit %)"
  echo "--------------------------------------"
  if [ -n "${PER_STRAT_MINMAX}" ]; then
    printf "%s\n" "${PER_STRAT_MINMAX}" | while IFS=$'\t' read -r s vmin mindesc vmax maxdesc; do
      printf "%-30s  min: %7.3f%%  (%s)    max: %7.3f%%  (%s)\n" "$s" "$vmin" "$mindesc" "$vmax" "$maxdesc"
    done
  else
    echo "(no per-strategy values parsed)"
  fi
} > "${SUMMARY_FILE}"

echo "Summary saved to: ${SUMMARY_FILE}"

# Cleanup temp file
[ -f "${TMP_ALLPROF}" ] && rm -f "${TMP_ALLPROF}"