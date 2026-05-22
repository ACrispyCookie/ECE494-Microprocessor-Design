# Called by report.sh:
#   vivado -mode batch -source parse-reports-scripts/export-reports.tcl \
#     -tclargs <repo_root> <project_xpr> <experiment> <report_type>
#
# report_type:
#   all
#   timing-summary
#   worst-paths
#   path-csv
#   utilization
#   power

proc usage {} {
    puts "Usage:"
    puts "  vivado -mode batch -source export-reports.tcl -tclargs <repo_root> <project_xpr> <experiment> <report_type>"
    puts ""
    puts "report_type:"
    puts "  all | timing-summary | worst-paths | path-csv | utilization | power"
}

if {$argc != 4} {
    usage
    error "Invalid number of arguments"
}

set repo_root   [file normalize [lindex $argv 0]]
set project_xpr [file normalize [lindex $argv 1]]
set experiment  [lindex $argv 2]
set report_type [lindex $argv 3]

set report_dir [file join $repo_root "reports" $experiment]
file mkdir $report_dir

puts "========================================"
puts "Vivado report export"
puts "========================================"
puts "repo_root   = $repo_root"
puts "project_xpr = $project_xpr"
puts "experiment  = $experiment"
puts "report_type = $report_type"
puts "report_dir  = $report_dir"
puts "========================================"

if {![file exists $project_xpr]} {
    error "Project not found: $project_xpr"
}

proc safe_get_property {prop obj} {
    if {[catch {set value [get_property $prop $obj]}]} {
        return ""
    }
    return $value
}

proc csv_clean {s} {
    # Keep CSV simple: remove commas/newlines from cell strings.
    set s [string map {"," ";" "\n" " " "\r" " "} $s]
    return $s
}

proc should_run {requested name} {
    return [expr {$requested eq "all" || $requested eq $name}]
}

open_project $project_xpr

# Reports below require an implemented design.
# If impl_1 is not complete, this will fail clearly.
if {[catch {open_run impl_1} err]} {
    puts "ERROR: Could not open implementation run impl_1."
    puts "Make sure implementation has completed successfully."
    puts "Original error:"
    puts $err
    error "Cannot export reports without implemented design"
}

# ------------------------------------------------------------
# Utilization
# ------------------------------------------------------------

if {[should_run $report_type "utilization"]} {
    puts "Exporting utilization reports..."

    report_utilization \
        -file [file join $report_dir "utilization.rpt"]

    report_utilization \
        -hierarchical \
        -file [file join $report_dir "utilization_hierarchical.rpt"]
}

# ------------------------------------------------------------
# Timing summary
# ------------------------------------------------------------

if {[should_run $report_type "timing-summary"]} {
    puts "Exporting timing summary..."

    report_timing_summary \
        -delay_type max \
        -report_unconstrained \
        -check_timing_verbose \
        -max_paths 1000 \
        -file [file join $report_dir "timing_summary_1000_paths.rpt"]
}

# ------------------------------------------------------------
# Worst paths detailed timing report
# ------------------------------------------------------------

if {[should_run $report_type "worst-paths"]} {
    puts "Exporting detailed worst timing paths..."

    report_timing \
        -delay_type max \
        -sort_by slack \
        -max_paths 1000 \
        -nworst 1 \
        -path_type full_clock_expanded \
        -file [file join $report_dir "worst_1000_paths.rpt"]

    report_timing \
        -delay_type max \
        -sort_by slack \
        -max_paths 10 \
        -nworst 1 \
        -path_type full_clock_expanded \
        -file [file join $report_dir "critical_paths_top10.rpt"]
}

# ------------------------------------------------------------
# Timing paths CSV for histograms
# ------------------------------------------------------------

if {[should_run $report_type "path-csv"]} {
    puts "Exporting timing paths CSV..."

    set paths [get_timing_paths \
        -delay_type max \
        -max_paths 5000 \
        -sort_by slack]

    set csv_file [file join $report_dir "timing_paths.csv"]
    set fp [open $csv_file "w"]

    puts $fp "index,slack,requirement,datapath_delay,logic_levels,startpoint,endpoint,path_group"

    set i 0
    foreach p $paths {
        set slack          [safe_get_property SLACK $p]
        set requirement    [safe_get_property REQUIREMENT $p]
        set datapath_delay [safe_get_property DATAPATH_DELAY $p]
        set logic_levels   [safe_get_property LOGIC_LEVELS $p]
        set startpoint     [csv_clean [safe_get_property STARTPOINT_PIN $p]]
        set endpoint       [csv_clean [safe_get_property ENDPOINT_PIN $p]]
        set path_group     [csv_clean [safe_get_property PATH_GROUP $p]]

        puts $fp "$i,$slack,$requirement,$datapath_delay,$logic_levels,$startpoint,$endpoint,$path_group"
        incr i
    }

    close $fp

    puts "Wrote $csv_file"
}

# ------------------------------------------------------------
# Power
# ------------------------------------------------------------

if {[should_run $report_type "power"]} {
    puts "Exporting power report..."

    report_power \
        -file [file join $report_dir "power.rpt"]
}

# ------------------------------------------------------------
# Metadata
# ------------------------------------------------------------

set meta_file [file join $report_dir "metadata.txt"]
set fp [open $meta_file "w"]

puts $fp "experiment=$experiment"
puts $fp "report_type=$report_type"
puts $fp "project_xpr=$project_xpr"
puts $fp "repo_root=$repo_root"
puts $fp "vivado_version=[version]"
puts $fp "date=[clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"

if {[file exists [file join $repo_root ".git"]]} {
    if {![catch {exec git -C $repo_root rev-parse HEAD} git_hash]} {
        puts $fp "repo_commit=$git_hash"
    }

    if {![catch {exec git -C [file join $repo_root "cv32e40p"] rev-parse HEAD} core_hash]} {
        puts $fp "cv32e40p_commit=$core_hash"
    }
}

close $fp

puts "========================================"
puts "Report export complete"
puts "Output directory:"
puts "  $report_dir"
puts "========================================"

close_project