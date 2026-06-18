#!/usr/bin/env bash
set -euo pipefail

# ------------------------------------------------------------
# Report CLI / source of truth
# ------------------------------------------------------------
# Examples:
#   ./report.sh -e baseline -r utilization -y
#   ./report.sh -e no-mul-forwarding -r timing -y
#   ./report.sh -e no-alu-forwarding -r utilization -y
#   ./report.sh -e no-alu-mul-forwarding -r timing -y
#   ./report.sh --comparison -r all --create-projects --stage post-implementation -y
#   ./report.sh --comparison -r power -y
#   ./report.sh --comparison -r timing --stage post-implementation -y
#   VIVADO=/path/to/vivado ./report.sh --comparison -r path-distribution -y
# ------------------------------------------------------------

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"
DEFAULT_REPORT_TCL="${REPO_ROOT}/parse-reports-scripts/export-reports.tcl"

VIVADO_BIN="${VIVADO:-vivado}"
REPORT_TCL="${DEFAULT_REPORT_TCL}"
PROJECT_XPR=""
EXPERIMENT=""
REPORT_TYPE=""
REPORT_STAGE="auto"
ASSUME_YES=0
RUN_PLOTS=1
CREATE_PROJECTS=0
NO_CREATE_PROJECTS=0
RUN_IMPLEMENTATION=0

VALID_EXPERIMENTS=("baseline" "no-mul-forwarding" "no-alu-forwarding" "no-alu-mul-forwarding")
VALID_REPORT_TYPES=("all" "utilization" "timing" "timing-summary" "worst-paths" "path-csv" "path-distribution" "power")
VALID_REPORT_STAGES=("auto" "post-synthesis" "post-implementation")

print_help() {
    cat <<EOF
Usage:
  ./report.sh [options]

Options:
  -e, --experiment NAME      Experiment to report. Valid built-ins:
                               baseline
                               no-mul-forwarding
                               no-alu-forwarding
                               no-alu-mul-forwarding
                             Use 'all' as shorthand for --comparison.

      --comparison           Run the selected report flow for all built-in
                             experiments and regenerate comparison plots.

  -r, --report TYPE          Report type. Valid values:
                               utilization        utilization.rpt + utilization_hierarchical.rpt
                               timing-summary     timing_summary_1000_paths.rpt
                               worst-paths        worst_1000_paths.rpt + critical_paths_top10.rpt
                               path-csv           timing_paths.csv for histograms/distributions
                               path-distribution  alias for path-csv + timing plots
                               power              power.rpt + power_metrics.csv + power plot
                               timing             timing-summary + worst-paths + path-csv
                               all                utilization + timing + path-csv + power

  -s, --stage STAGE          Timing/utilization report stage. Valid values:
                               auto                 open impl_1 if available, otherwise
                                                    generate post-synthesis reports (default)
                               post-synthesis       always synthesize current design and report
                                                    the post-synthesis netlist
                               post-implementation  report implemented impl_1 design; fail if
                                                    implementation has not completed

  -p, --project PATH         Path to Vivado .xpr project. Only valid for a
                             single experiment. Default:
                               build/vivado-<experiment>/cv32e40p-zedboard-project.xpr

  -t, --tcl PATH             Path to report export Tcl script. Default:
                               ${DEFAULT_REPORT_TCL}

      --vivado PATH          Vivado executable. Default: \${VIVADO:-vivado}

      --create-projects      Recreate/update Vivado projects before reporting.
                             If --stage post-implementation is selected, also
                             run an in-memory implementation before exporting reports.
                             If omitted, missing built-in projects are created
                             automatically.

      --no-create-projects   Never create missing Vivado projects; fail if the
                             selected project does not exist.

      --plots                Regenerate relevant comparison plots after reports.
                             Default: enabled.

      --no-plots             Do not regenerate comparison plots.

  -y, --yes                  Do not ask for confirmation.
  -h, --help                 Show this help message.

Examples:
  ./report.sh -e baseline -r utilization -y
  ./report.sh -e baseline -r timing-summary -y
  ./report.sh -e no-mul-forwarding -r timing --stage post-synthesis -y
  ./report.sh -e no-mul-forwarding -r timing --stage post-implementation -y
  ./report.sh -e no-mul-forwarding -r path-distribution -y
  ./report.sh -e no-alu-forwarding -r utilization -y
  ./report.sh -e no-alu-mul-forwarding -r timing -y
  ./report.sh --comparison -r all --create-projects --stage post-implementation -y
  ./report.sh --comparison -r power -y

Outputs:
  reports/<experiment>/                  raw Vivado reports/CSVs/metadata
  reports/summary/*.csv                  comparison summaries
  reports/plots/*.svg                    comparison plots
EOF
}

default_project_xpr_for_experiment() {
    local experiment="$1"
    printf '%s/build/vivado-%s/cv32e40p-zedboard-project.xpr' "${REPO_ROOT}" "${experiment}"
}

is_builtin_experiment() {
    local value="$1"
    local item
    for item in "${VALID_EXPERIMENTS[@]}"; do
        [[ "${value}" == "${item}" ]] && return 0
    done
    return 1
}

is_valid_report_type() {
    local value="$1"
    local item
    for item in "${VALID_REPORT_TYPES[@]}"; do
        [[ "${value}" == "${item}" ]] && return 0
    done
    return 1
}

normalize_report_stage() {
    local value="$1"
    case "${value}" in
        auto) printf 'auto' ;;
        post-synthesis|post_synthesis|synthesis|synth) printf 'post-synthesis' ;;
        post-implementation|post_implementation|implementation|impl) printf 'post-implementation' ;;
        *) return 1 ;;
    esac
}

is_valid_report_stage() {
    normalize_report_stage "$1" >/dev/null
}

prompt_experiment() {
    echo "========================================"
    echo "Vivado Report CLI"
    echo "========================================"
    echo
    echo "Select experiment:"
    echo "  1) baseline"
    echo "  2) no-mul-forwarding"
    echo "  3) no-alu-forwarding"
    echo "  4) no-alu-mul-forwarding"
    echo "  5) all / comparison"
    echo "  6) custom"
    echo
    read -rp "Experiment [1-6]: " exp_choice
    case "${exp_choice}" in
        1) EXPERIMENT="baseline" ;;
        2) EXPERIMENT="no-mul-forwarding" ;;
        3) EXPERIMENT="no-alu-forwarding" ;;
        4) EXPERIMENT="no-alu-mul-forwarding" ;;
        5) EXPERIMENT="all" ;;
        6)
            read -rp "Custom experiment name: " EXPERIMENT
            [[ -n "${EXPERIMENT}" ]] || { echo "ERROR: Experiment cannot be empty." >&2; exit 1; }
            ;;
        *) echo "ERROR: Invalid experiment choice." >&2; exit 1 ;;
    esac
}

prompt_report_type() {
    echo
    echo "Select report type:"
    echo "  1) all"
    echo "  2) utilization"
    echo "  3) timing"
    echo "  4) timing-summary"
    echo "  5) worst-paths"
    echo "  6) path-distribution"
    echo "  7) power"
    echo
    read -rp "Report type [1-7]: " report_choice
    case "${report_choice}" in
        1) REPORT_TYPE="all" ;;
        2) REPORT_TYPE="utilization" ;;
        3) REPORT_TYPE="timing" ;;
        4) REPORT_TYPE="timing-summary" ;;
        5) REPORT_TYPE="worst-paths" ;;
        6) REPORT_TYPE="path-distribution" ;;
        7) REPORT_TYPE="power" ;;
        *) echo "ERROR: Invalid report type." >&2; exit 1 ;;
    esac
}

prompt_report_stage() {
    echo
    echo "Select report stage:"
    echo "  1) auto (implementation if available, otherwise post-synthesis)"
    echo "  2) post-synthesis"
    echo "  3) post-implementation"
    echo
    read -rp "Report stage [1-3, default 1]: " stage_choice
    case "${stage_choice:-1}" in
        1) REPORT_STAGE="auto" ;;
        2) REPORT_STAGE="post-synthesis" ;;
        3) REPORT_STAGE="post-implementation" ;;
        *) echo "ERROR: Invalid report stage." >&2; exit 1 ;;
    esac
}

setup_vivado_compat() {
    # Vivado 2022.2 expects en_US.UTF-8 and libtinfo.so.5. Minimal containers
    # often have C.utf8 and libtinfo.so.6 only; use non-root compatibility shims.
    if ! locale -a 2>/dev/null | grep -qi '^en_US\.utf-8$'; then
        mkdir -p /tmp/hermes-locales
        if [[ -d /usr/lib/locale/C.utf8 ]]; then
            ln -sfn /usr/lib/locale/C.utf8 /tmp/hermes-locales/en_US.UTF-8
            export LOCPATH="/tmp/hermes-locales${LOCPATH:+:${LOCPATH}}"
        fi
    fi

    if ! ldconfig -p 2>/dev/null | grep -q 'libtinfo.so.5'; then
        local compat_lib_dir="${REPO_ROOT}/.vivado-compat/lib"
        mkdir -p "${compat_lib_dir}"
        if [[ -e /lib/x86_64-linux-gnu/libtinfo.so.6 ]]; then
            ln -sfn /lib/x86_64-linux-gnu/libtinfo.so.6 "${compat_lib_dir}/libtinfo.so.5"
            export LD_LIBRARY_PATH="${compat_lib_dir}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
        fi
    fi
}

create_project_if_needed() {
    local experiment="$1"
    local project_xpr="$2"

    if [[ "${CREATE_PROJECTS}" -eq 1 ]]; then
        echo
        echo "Creating/updating Vivado project for ${experiment}..."
        make -C "${REPO_ROOT}" "${experiment}" VIVADO="${VIVADO_BIN}"
    elif [[ "${NO_CREATE_PROJECTS}" -eq 0 && ! -f "${project_xpr}" ]] && is_builtin_experiment "${experiment}"; then
        echo
        echo "Vivado project missing; creating project for ${experiment}..."
        make -C "${REPO_ROOT}" "${experiment}" VIVADO="${VIVADO_BIN}"
    fi
}

run_report_for_experiment() {
    local experiment="$1"
    local project_xpr="$2"
    local report_dir="${REPO_ROOT}/reports/${experiment}"

    if [[ "${experiment}" == */* || -z "${experiment}" ]]; then
        echo "ERROR: Invalid experiment name: ${experiment}" >&2
        exit 1
    fi

    create_project_if_needed "${experiment}" "${project_xpr}"

    if [[ ! -f "${project_xpr}" ]]; then
        echo "ERROR: Vivado project not found:" >&2
        echo "  ${project_xpr}" >&2
        echo "Create it first with: make ${experiment}" >&2
        exit 1
    fi

    mkdir -p "${report_dir}"
    echo
    echo "========================================"
    echo "Running report"
    echo "========================================"
    echo "Experiment  : ${experiment}"
    echo "Report type : ${REPORT_TYPE}"
    echo "Report stage: ${REPORT_STAGE}"
    echo "Run impl.   : ${RUN_IMPLEMENTATION}"
    echo "Project     : ${project_xpr}"
    echo "Output dir  : ${report_dir}"
    echo

    "${VIVADO_BIN}" -mode batch \
        -source "${REPORT_TCL}" \
        -tclargs "${REPO_ROOT}" "${project_xpr}" "${experiment}" "${REPORT_TYPE}" "${REPORT_STAGE}" "${RUN_IMPLEMENTATION}"

    if [[ "${REPORT_TYPE}" == "all" || "${REPORT_TYPE}" == "power" ]]; then
        echo
        echo "Post-processing power report for ${experiment}..."
        if [[ "${RUN_PLOTS}" -eq 1 ]]; then
            python3 "${REPO_ROOT}/scripts/plot-power.py" \
                --reports-dir "${REPO_ROOT}/reports" \
                --experiments "${experiment}" \
                --summary-csv "${report_dir}/power_metrics_summary.csv" \
                --svg "${report_dir}/power_compare.svg"
        else
            python3 "${REPO_ROOT}/scripts/plot-power.py" \
                --reports-dir "${REPO_ROOT}/reports" \
                --experiments "${experiment}" \
                --summary-csv "${report_dir}/power_metrics_summary.csv" \
                --svg "${report_dir}/power_compare.svg" \
                --no-svg
        fi
    fi

    echo
    echo "Done. Reports written to:"
    echo "  ${report_dir}"
    find "${report_dir}" -maxdepth 1 -type f | sort
}

run_plots() {
    local report_type="$1"
    local comparison="$2"

    [[ "${RUN_PLOTS}" -eq 1 ]] || return 0
    [[ "${comparison}" -eq 1 ]] || return 0

    case "${report_type}" in
        all|utilization)
            python3 "${REPO_ROOT}/scripts/plot-utilization.py"
            ;;&
        all|timing|path-csv|path-distribution)
            python3 "${REPO_ROOT}/scripts/plot-timing.py"
            ;;&
        all|power)
            python3 "${REPO_ROOT}/scripts/plot-power.py"
            ;;
    esac

    if [[ "${report_type}" == "all" ]]; then
        python3 "${REPO_ROOT}/scripts/plot-presentation-summary.py"
    fi
}

# ------------------------------------------------------------
# Parse arguments
# ------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        -e|--experiment)
            [[ $# -ge 2 ]] || { echo "ERROR: Missing value for $1" >&2; exit 1; }
            EXPERIMENT="$2"
            shift 2
            ;;
        --comparison|--compare)
            EXPERIMENT="all"
            shift
            ;;
        -r|--report)
            [[ $# -ge 2 ]] || { echo "ERROR: Missing value for $1" >&2; exit 1; }
            REPORT_TYPE="$2"
            shift 2
            ;;
        -s|--stage)
            [[ $# -ge 2 ]] || { echo "ERROR: Missing value for $1" >&2; exit 1; }
            REPORT_STAGE="$2"
            shift 2
            ;;
        -p|--project)
            [[ $# -ge 2 ]] || { echo "ERROR: Missing value for $1" >&2; exit 1; }
            PROJECT_XPR="$2"
            shift 2
            ;;
        -t|--tcl)
            [[ $# -ge 2 ]] || { echo "ERROR: Missing value for $1" >&2; exit 1; }
            REPORT_TCL="$2"
            shift 2
            ;;
        --vivado)
            [[ $# -ge 2 ]] || { echo "ERROR: Missing value for $1" >&2; exit 1; }
            VIVADO_BIN="$2"
            shift 2
            ;;
        --create-projects)
            CREATE_PROJECTS=1
            shift
            ;;
        --no-create-projects)
            NO_CREATE_PROJECTS=1
            shift
            ;;
        --plots)
            RUN_PLOTS=1
            shift
            ;;
        --no-plots)
            RUN_PLOTS=0
            shift
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

[[ -n "${EXPERIMENT}" ]] || prompt_experiment
[[ -n "${REPORT_TYPE}" ]] || prompt_report_type
[[ -n "${REPORT_STAGE}" ]] || prompt_report_stage

if ! is_valid_report_type "${REPORT_TYPE}"; then
    echo "ERROR: Invalid report type: ${REPORT_TYPE}" >&2
    printf "Valid report types:\n  %s\n" "${VALID_REPORT_TYPES[@]}" >&2
    exit 1
fi

if ! normalized_stage="$(normalize_report_stage "${REPORT_STAGE}")"; then
    echo "ERROR: Invalid report stage: ${REPORT_STAGE}" >&2
    printf "Valid report stages:\n  %s\n" "${VALID_REPORT_STAGES[@]}" >&2
    echo "Aliases accepted: synth, synthesis, impl, implementation, post_synthesis, post_implementation" >&2
    exit 1
fi
REPORT_STAGE="${normalized_stage}"

if [[ "${REPORT_STAGE}" == "post-implementation" && "${CREATE_PROJECTS}" -eq 1 ]]; then
    RUN_IMPLEMENTATION=1
fi

if [[ "${EXPERIMENT}" == "all" && -n "${PROJECT_XPR}" ]]; then
    echo "ERROR: --project cannot be used with --comparison / -e all." >&2
    exit 1
fi

if [[ ! -f "${REPORT_TCL}" ]]; then
    echo "ERROR: Missing Tcl script: ${REPORT_TCL}" >&2
    exit 1
fi

if ! command -v "${VIVADO_BIN}" >/dev/null 2>&1; then
    echo "ERROR: Vivado executable not found: ${VIVADO_BIN}" >&2
    echo "Set VIVADO=/path/to/vivado or use --vivado /path/to/vivado." >&2
    exit 1
fi

setup_vivado_compat

comparison=0
experiments=()
if [[ "${EXPERIMENT}" == "all" ]]; then
    comparison=1
    experiments=("${VALID_EXPERIMENTS[@]}")
else
    experiments=("${EXPERIMENT}")
fi

if [[ "${ASSUME_YES}" -ne 1 ]]; then
    echo
    echo "========================================"
    echo "Configuration"
    echo "========================================"
    echo "Repo root   : ${REPO_ROOT}"
    echo "Vivado      : ${VIVADO_BIN}"
    echo "Tcl script  : ${REPORT_TCL}"
    echo "Experiments : ${experiments[*]}"
    echo "Report type : ${REPORT_TYPE}"
    echo "Report stage: ${REPORT_STAGE}"
    echo "Run impl.   : ${RUN_IMPLEMENTATION}"
    echo "Plots       : ${RUN_PLOTS}"
    read -rp "Continue? [y/N]: " confirm
    case "${confirm}" in
        y|Y|yes|YES) ;;
        *) echo "Cancelled."; exit 0 ;;
    esac
fi

for experiment in "${experiments[@]}"; do
    project_xpr="${PROJECT_XPR:-$(default_project_xpr_for_experiment "${experiment}")}" 
    run_report_for_experiment "${experiment}" "${project_xpr}"
done

run_plots "${REPORT_TYPE}" "${comparison}"
