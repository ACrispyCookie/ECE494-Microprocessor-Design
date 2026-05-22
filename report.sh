#!/usr/bin/env bash
set -euo pipefail

# ------------------------------------------------------------
# Report export helper
# ------------------------------------------------------------
#
# Interactive:
#   ./report.sh
#
# Non-interactive:
#   ./report.sh -e baseline -r utilization -y
#   ./report.sh -e baseline -r all -y
#   ./report.sh -e no-mul-forwarding -r worst-paths -y
#
# Optional:
#   VIVADO=/path/to/vivado ./report.sh
#   ./report.sh --vivado /path/to/vivado -e baseline -r all -y
# ------------------------------------------------------------

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"

DEFAULT_PROJECT_XPR="${REPO_ROOT}/build/vivado/cv32e40p-zedboard-project.xpr"
DEFAULT_REPORT_TCL="${REPO_ROOT}/parse-reports-scripts/export-reports.tcl"

VIVADO_BIN="${VIVADO:-vivado}"
PROJECT_XPR="${DEFAULT_PROJECT_XPR}"
REPORT_TCL="${DEFAULT_REPORT_TCL}"

EXPERIMENT=""
REPORT_TYPE=""
ASSUME_YES=0

VALID_EXPERIMENTS=("baseline" "no-mul-forwarding")
VALID_REPORT_TYPES=("all" "timing-summary" "worst-paths" "path-csv" "utilization" "power")

print_help() {
    cat <<EOF
Usage:
  ./report.sh [options]

Options:
  -e, --experiment NAME      Experiment name.
                             Common values:
                               baseline
                               no-mul-forwarding

  -r, --report TYPE          Report type.
                             Valid values:
                               all
                               timing-summary
                               worst-paths
                               path-csv
                               utilization
                               power

  -p, --project PATH         Path to Vivado .xpr project.
                             Default:
                               ${DEFAULT_PROJECT_XPR}

  -t, --tcl PATH             Path to report export Tcl script.
                             Default:
                               ${DEFAULT_REPORT_TCL}

      --vivado PATH          Vivado executable to use.
                             Default:
                               vivado
                             Can also be set via:
                               VIVADO=/path/to/vivado

  -y, --yes                  Do not ask for confirmation.

  -h, --help                 Show this help message.

Examples:
  ./report.sh

  ./report.sh -e baseline -r utilization

  ./report.sh -e baseline -r all -y

  ./report.sh -e no-mul-forwarding -r worst-paths -y

  VIVADO=/media/storage/Vivado/2022.2/bin/vivado ./report.sh -e baseline -r all -y

Output:
  Reports are written to:
    reports/<experiment>/

EOF
}

is_valid_report_type() {
    local value="$1"

    for item in "${VALID_REPORT_TYPES[@]}"; do
        if [[ "${value}" == "${item}" ]]; then
            return 0
        fi
    done

    return 1
}

prompt_experiment() {
    echo "========================================"
    echo "Vivado Report Export"
    echo "========================================"
    echo
    echo "Select experiment:"
    echo "  1) baseline"
    echo "  2) no-mul-forwarding"
    echo "  3) custom"
    echo

    read -rp "Experiment [1-3]: " exp_choice

    case "${exp_choice}" in
        1)
            EXPERIMENT="baseline"
            ;;
        2)
            EXPERIMENT="no-mul-forwarding"
            ;;
        3)
            read -rp "Custom experiment name: " EXPERIMENT
            if [[ -z "${EXPERIMENT}" ]]; then
                echo "ERROR: Experiment name cannot be empty." >&2
                exit 1
            fi
            ;;
        *)
            echo "ERROR: Invalid experiment choice." >&2
            exit 1
            ;;
    esac
}

prompt_report_type() {
    echo
    echo "Select report type:"
    echo "  1) all"
    echo "  2) timing-summary"
    echo "  3) worst-paths"
    echo "  4) path-csv"
    echo "  5) utilization"
    echo "  6) power"
    echo

    read -rp "Report type [1-6]: " report_choice

    case "${report_choice}" in
        1)
            REPORT_TYPE="all"
            ;;
        2)
            REPORT_TYPE="timing-summary"
            ;;
        3)
            REPORT_TYPE="worst-paths"
            ;;
        4)
            REPORT_TYPE="path-csv"
            ;;
        5)
            REPORT_TYPE="utilization"
            ;;
        6)
            REPORT_TYPE="power"
            ;;
        *)
            echo "ERROR: Invalid report type." >&2
            exit 1
            ;;
    esac
}

# ------------------------------------------------------------
# Parse arguments
# ------------------------------------------------------------

while [[ $# -gt 0 ]]; do
    case "$1" in
        -e|--experiment)
            if [[ $# -lt 2 ]]; then
                echo "ERROR: Missing value for $1" >&2
                exit 1
            fi
            EXPERIMENT="$2"
            shift 2
            ;;
        -r|--report)
            if [[ $# -lt 2 ]]; then
                echo "ERROR: Missing value for $1" >&2
                exit 1
            fi
            REPORT_TYPE="$2"
            shift 2
            ;;
        -p|--project)
            if [[ $# -lt 2 ]]; then
                echo "ERROR: Missing value for $1" >&2
                exit 1
            fi
            PROJECT_XPR="$2"
            shift 2
            ;;
        -t|--tcl)
            if [[ $# -lt 2 ]]; then
                echo "ERROR: Missing value for $1" >&2
                exit 1
            fi
            REPORT_TCL="$2"
            shift 2
            ;;
        --vivado)
            if [[ $# -lt 2 ]]; then
                echo "ERROR: Missing value for $1" >&2
                exit 1
            fi
            VIVADO_BIN="$2"
            shift 2
            ;;
        -y|--yes)
            ASSUME_YES=1
            shift
            ;;
        -h|--help)
            print_help
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option: $1" >&2
            echo
            print_help
            exit 1
            ;;
    esac
done

# ------------------------------------------------------------
# Prompt missing values
# ------------------------------------------------------------

if [[ -z "${EXPERIMENT}" ]]; then
    prompt_experiment
fi

if [[ -z "${REPORT_TYPE}" ]]; then
    prompt_report_type
fi

# ------------------------------------------------------------
# Validate configuration
# ------------------------------------------------------------

if ! is_valid_report_type "${REPORT_TYPE}"; then
    echo "ERROR: Invalid report type: ${REPORT_TYPE}" >&2
    echo "Valid report types:" >&2
    printf "  %s\n" "${VALID_REPORT_TYPES[@]}" >&2
    exit 1
fi

if [[ "${EXPERIMENT}" == */* ]]; then
    echo "ERROR: Experiment name must not contain '/': ${EXPERIMENT}" >&2
    exit 1
fi

if [[ -z "${EXPERIMENT}" ]]; then
    echo "ERROR: Experiment name cannot be empty." >&2
    exit 1
fi

if ! command -v "${VIVADO_BIN}" >/dev/null 2>&1; then
    echo "ERROR: Vivado executable not found: ${VIVADO_BIN}" >&2
    echo "Set VIVADO=/path/to/vivado or use --vivado /path/to/vivado." >&2
    exit 1
fi

if [[ ! -f "${REPORT_TCL}" ]]; then
    echo "ERROR: Missing Tcl script: ${REPORT_TCL}" >&2
    exit 1
fi

if [[ ! -f "${PROJECT_XPR}" ]]; then
    echo "ERROR: Vivado project not found:"
    echo "  ${PROJECT_XPR}"
    echo
    echo "Create it first with:"
    echo "  vivado -source cv32e40p-zedboard-project.tcl"
    echo "or:"
    echo "  make"
    exit 1
fi

REPORT_DIR="${REPO_ROOT}/reports/${EXPERIMENT}"
mkdir -p "${REPORT_DIR}"

echo
echo "========================================"
echo "Configuration"
echo "========================================"
echo "Repo root   : ${REPO_ROOT}"
echo "Vivado      : ${VIVADO_BIN}"
echo "Project     : ${PROJECT_XPR}"
echo "Tcl script  : ${REPORT_TCL}"
echo "Experiment  : ${EXPERIMENT}"
echo "Report type : ${REPORT_TYPE}"
echo "Output dir  : ${REPORT_DIR}"
echo

if [[ "${ASSUME_YES}" -ne 1 ]]; then
    read -rp "Continue? [y/N]: " confirm

    case "${confirm}" in
        y|Y|yes|YES)
            ;;
        *)
            echo "Cancelled."
            exit 0
            ;;
    esac
fi

echo
echo "Running Vivado..."
echo

"${VIVADO_BIN}" -mode batch \
    -source "${REPORT_TCL}" \
    -tclargs "${REPO_ROOT}" "${PROJECT_XPR}" "${EXPERIMENT}" "${REPORT_TYPE}"

echo
echo "Done. Reports written to:"
echo "  ${REPORT_DIR}"
echo

find "${REPORT_DIR}" -maxdepth 1 -type f | sort