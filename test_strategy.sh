#!/usr/bin/env bash
VERBOSE=0
debug() { if [[ "$VERBOSE" -eq 1 ]]; then printf "[DEBUG] %s\n" "$*"; fi; }
MODE="summary"
CONFIG="config.json"

# --- Parse arguments ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    -m|--mode)
      MODE="${2:-summary}"
      shift 2
      ;;
    -c|--config)
      CONFIG="${2:-config.json}"
      shift 2
      ;;
    -v|--verbose)
      VERBOSE=1
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [-m summary|full] [-c config.json] STRATEGY_NAME"
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
    *)
      STRAT="$1"
      shift
      ;;
  esac
done

# Defer strict mode until after basic vars exist
SHELL_BIN="$(ps -o comm= -p "$$" 2>/dev/null || true)"
debug "Running with shell: ${SHELL_BIN:-unknown}"
debug "Bash version: ${BASH_VERSION:-unknown}"
debug "Mode: $MODE  Config: $CONFIG"

set -euo pipefail

if [[ -z "${STRAT:-}" ]]; then
  echo "Error: STRATEGY_NAME is required." >&2
  echo "Usage: $0 [-m summary|full] [-c config.json] STRATEGY_NAME" >&2
  exit 1
fi

if [[ ! -f "$CONFIG" ]]; then
  echo "Error: config file '$CONFIG' not found." >&2
  exit 1
fi

if ! command -v freqtrade >/dev/null 2>&1; then
  echo "Error: 'freqtrade' CLI not found in PATH." >&2
  exit 1
fi

debug "Strategy: $STRAT"

debug "Using config: $CONFIG"

# Normalized strategy name for filesystem paths (lowercase, non-alnum -> '-')
STRAT_NORM="$(printf '%s' "${STRAT}" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g')"

# --- Timeranges to test (4 blocks) --- (Bash 3.2 compatible, POSIX-safe heredoc)
TESTS="$(cat <<'EOF'
train_2024_9m|20240401-20241231
oos_2025_6m|20250101-20250630
bear_2022|20220401-20221231
chop_2023|20230301-20231001
EOF
)"

WORKDIR="$PWD/user_data/test_strategy_logs/${STRAT_NORM}/$(date +%Y%m%d_%H%M%S)"
LOGDIR="${WORKDIR}/logs"
RESDIR="${WORKDIR}/results"
mkdir -p "$LOGDIR" "$RESDIR"
echo "Working directory: $WORKDIR"


# Colors (only if terminal supports)
if [[ -t 1 ]]; then
  BOLD="$(printf '\033[1m')"; DIM="$(printf '\033[2m')"; RESET="$(printf '\033[0m')"
else
  BOLD=""; DIM=""; RESET=""
fi

# --- Header and ASCII table renderers ---
print_header () {
  # Print a clean header (intestazione) for the summary block
  local now; now="$(date '+%Y-%m-%d %H:%M:%S')"
  echo
  echo "================================ SUMMARY ================================="
  echo "Strategy    : ${STRAT}"
  echo "Config      : ${CONFIG}"
  echo "Generated   : ${now}"
  echo "Workdir     : ${WORKDIR}"
  echo "========================================================================="
}

ascii_table () {
  # Renders a TSV (pipe-separated) file as a neat ASCII table with header.
  # Usage: ascii_table path/to/summary.tsv
  local file="$1"
  awk -F'|' '
    function trim(s) { sub(/^\s+/, "", s); sub(/\s+$/, "", s); return s }
    function rep(n,  s,i) { s=""; for (i=0; i<n; i++) s=s "-"; return s }
    NR==1 {
      # store header separately
    }
    {
      for (i = 1; i <= NF; i++) {
        gsub(/[\r\n]/, "", $i)
        cell = trim($i)
        data[NR,i] = cell
        if (length(cell) > w[i]) w[i] = length(cell)
      }
      if (NF > maxNF) maxNF = NF
      rows = NR
    }
    END {
      # build separator line
      sep = "+"
      for (i = 1; i <= maxNF; i++) sep = sep rep(w[i] + 2) "+"

      print sep
      # header (row 1)
      printf "|"
      for (i = 1; i <= maxNF; i++) printf " %-*s |", w[i], data[1,i]
      print ""
      print sep
      # body (rows 2..N)
      for (r = 2; r <= rows; r++) {
        printf "|"
        for (i = 1; i <= maxNF; i++) printf " %-*s |", w[i], data[r,i]
        print ""
      }
      print sep
    }
  ' "$file"
}

# --- Helper: parse key metrics from a backtesting log ---
# We try to extract: TOTAL PROFIT %, PROFIT FACTOR, DRAWDOWN %
parse_metrics () {
  local logfile="$1"
  local total_profit="" profit_factor="" drawdown=""

  # Normalize potential Unicode minus signs and odd spaces in the log stream on-the-fly.
  # Some terminals/libs print "−" (U+2212). Our regexes only match ASCII "-".
  # We'll run all extractions through a sed filter that maps these to ASCII.
  local SED_FIX='s/−/-/g; s/—/-/g; s/–/-/g; s/﹣/-/g; s/﻿//g'

  # --- Try modern "SUMMARY METRICS" first: "Total profit %", "Profit factor", "Absolute drawdown (...%)" ---
  # Total profit %
  total_profit="$(
    grep -Ei '(^|[^A-Za-z])Total profit %' "$logfile" \
    | head -n1 \
    | sed -E "$SED_FIX" \
    | sed -E 's/.*Total profit %[^0-9+\-]*([+\-]?[0-9]+(\.[0-9]+)?).*/\1%/I' \
    || true
  )"

  # Profit factor
  profit_factor="$(
    grep -Ei 'Profit factor' "$logfile" \
    | head -n1 \
    | sed -E "$SED_FIX" \
    | sed -E 's/.*Profit factor[^0-9+\-]*([+\-]?[0-9]+(\.[0-9]+)?).*/\1/I' \
    || true
  )"

  # Drawdown % (try "Absolute drawdown ... (x.xx%)" first)
  drawdown="$(
    grep -Ei 'Absolute drawdown' "$logfile" \
    | head -n1 \
    | sed -E "$SED_FIX" \
    | grep -Eo '[+-]?[0-9]+(\.[0-9]+)?%' \
    | head -n1 \
    || true
  )"

  # --- Fallback: parse "STRATEGY SUMMARY" table row for the current strategy (2025.x format) ---
  if [[ -z "$total_profit" || -z "$drawdown" ]]; then
    local strat_row
    strat_row="$(
      awk '
        BEGIN { in_sum=0 }
        /STRATEGY SUMMARY/ { in_sum=1; next }
        in_sum && /\|/ {
          gsub(/│/, "|");
          if ($0 ~ /\|[[:space:]]*'"$STRAT"'[[:space:]]*\|/) {
            print $0; exit
          }
        }
      ' "$logfile" \
      | sed -E "$SED_FIX" \
      | sed -E "s/[[:cntrl:]]//g"
    )"

    if [[ -n "$strat_row" ]]; then
      # Field 6 is "Tot Profit %"
      if [[ -z "$total_profit" ]]; then
        local totp_field
        totp_field="$(echo "$strat_row" | awk -F'|' '{gsub(/^[[:space:]]+|[[:space:]]+$/, "", $6); print $6}')"
        if [[ -n "$totp_field" ]]; then
          case "$totp_field" in
            *% ) total_profit="$totp_field" ;;
             * ) total_profit="${totp_field}%" ;;
          esac
        fi
      fi

      # Field 9 contains drawdown like "41.977 USDT  4.20%"
      if [[ -z "$drawdown" ]]; then
        local dd_field
        dd_field="$(echo "$strat_row" | awk -F'|' '{gsub(/^[[:space:]]+|[[:space:]]+$/, "", $9); print $9}')"
        if [[ -n "$dd_field" ]]; then
          drawdown="$(echo "$dd_field" | grep -Eo '[+-]?[0-9]+(\.[0-9]+)?%' | tail -n1 || true)"
        fi
      fi
    fi
  fi

  # --- Legacy fallback (older FT formats that printed "TOTAL PROFIT" lines) ---
  if [[ -z "$total_profit" ]]; then
    total_profit="$(
      grep -Ei '(^|[^A-Za-z])(Total|TOTAL) profit' "$logfile" \
      | head -n1 \
      | sed -E "$SED_FIX" \
      | sed -E 's/.*(Total|TOTAL)[[:space:]]+profit[^0-9+\-]*([+\-]?[0-9]+(\.[0-9]+)?)%.*/\2%/I' \
      || true
    )"
  fi
  if [[ -z "$drawdown" ]]; then
    drawdown="$(
      grep -Ei '(^|[^A-Za-z])[Dd]rawdown([^A-Za-z]|$)' "$logfile" \
      | sed -E "$SED_FIX" \
      | grep -Eo '[+-]?[0-9]+(\.[0-9]+)?%' \
      | head -n1 \
      || true
    )"
  fi

  # Fallback defaults
  [[ -z "$total_profit" ]] && total_profit="n/a"
  [[ -z "$profit_factor" ]] && profit_factor="n/a"
  [[ -z "$drawdown" ]] && drawdown="n/a"

  echo "${total_profit}|${profit_factor}|${drawdown}"
}

# --- Run a single backtest and collect metrics ---
run_test () {
  local label="$1"
  local trange="$2"

  local resfile="${RESDIR}/${STRAT}_${label}.json"
  local logfile="${LOGDIR}/${STRAT}_${label}.log"

  echo "${BOLD}>>> Running backtesting: ${label} (${trange})${RESET}"
  debug "Result file: $resfile"
  debug "Log file: $logfile"
  # Run backtesting; export trades (for optional later plotting/analysis)
  if [[ "$MODE" == "summary" ]]; then
    # In summary mode, suppress freqtrade CLI output on the console and only log to file
    freqtrade backtesting -c "$CONFIG" -s "$STRAT" --timerange "$trange" \
      --export trades \
      --export-filename "$resfile" \
      >"$logfile" 2>&1
  else
    # In full mode, stream output to console and also save it to logfile
    freqtrade backtesting -c "$CONFIG" -s "$STRAT" --timerange "$trange" \
      --export trades \
      --export-filename "$resfile" \
      | tee "$logfile"
  fi

  # Parse metrics from the console log
  local parsed; parsed="$(parse_metrics "$logfile")"
  local total_profit="$(echo "$parsed" | cut -d'|' -f1)"
  local profit_factor="$(echo "$parsed" | cut -d'|' -f2)"
  local drawdown="$(echo "$parsed" | cut -d'|' -f3)"

  echo "$label|$trange|$total_profit|$profit_factor|$drawdown" >> "${WORKDIR}/summary.tsv"

  if [[ "$MODE" == "full" ]]; then
    echo
    echo "${DIM}--- [${label}] Raw log saved to:${RESET} $logfile"
    echo "${DIM}--- [${label}] Exported trades:${RESET} $resfile"
    echo
  fi
}

# --- Header for summary file ---
echo -e "label|timerange|total_profit|profit_factor|drawdown" > "${WORKDIR}/summary.tsv"

# --- Execute 4 tests ---
printf "%s\n" "$TESTS" | while IFS='|' read -r label trange; do
  run_test "$label" "$trange"
done

# --- Print Final Output ---
if [[ "$MODE" == "summary" ]]; then
  print_header
  ascii_table "${WORKDIR}/summary.tsv"
else
  echo "${BOLD}${STRAT}${RESET}"
  echo "${BOLD}Per-test outputs (logs) and exported trades are stored under:${RESET} $WORKDIR"
  echo
  echo "${BOLD}Summary:${RESET}"
  print_header
  ascii_table "${WORKDIR}/summary.tsv"
  echo
  echo "${DIM}Note:${RESET} Metrics are parsed from CLI output and may vary slightly across Freqtrade versions. Inspect logs for full details."
fi