# Called by report.sh:
#   vivado -mode batch -source parse-reports-scripts/export-reports.tcl \
#     -tclargs <repo_root> <project_xpr> <experiment> <report_type> ?report_stage? ?run_implementation?
#
# report_type:
#   all              utilization + timing-summary + worst-paths + path-csv + power
#   utilization
#   timing           timing-summary + worst-paths + path-csv
#   timing-summary
#   worst-paths
#   path-csv
#   path-distribution (alias for path-csv)
#   power            report_power output

proc usage {} {
    puts "Usage:"
    puts "  vivado -mode batch -source export-reports.tcl -tclargs <repo_root> <project_xpr> <experiment> <report_type> ?report_stage? ?run_implementation?"
    puts ""
    puts "report_type:"
    puts "  all | utilization | timing | timing-summary | worst-paths | path-csv | path-distribution | power"
    puts ""
    puts "report_stage:"
    puts "  auto | post-synthesis | post-implementation"
}

if {$argc < 4 || $argc > 6} {
    usage
    error "Invalid number of arguments"
}

set repo_root   [file normalize [lindex $argv 0]]
set project_xpr [file normalize [lindex $argv 1]]
set experiment  [lindex $argv 2]
set report_type [lindex $argv 3]
set requested_stage "auto"
set run_implementation 0
if {$argc >= 5} {
    set requested_stage [lindex $argv 4]
}
if {$argc >= 6} {
    set run_implementation [lindex $argv 5]
}

set report_dir [file join $repo_root "reports" $experiment]
file mkdir $report_dir

puts "========================================"
puts "Vivado report export"
puts "========================================"
puts "repo_root   = $repo_root"
puts "project_xpr = $project_xpr"
puts "experiment  = $experiment"
puts "report_type = $report_type"
puts "report_stage= $requested_stage"
puts "run_impl    = $run_implementation"
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
    if {$requested eq $name} { return 1 }
    if {$requested eq "all"} { return 1 }
    if {$requested eq "timing" && ($name eq "timing-summary" || $name eq "worst-paths" || $name eq "path-csv")} { return 1 }
    if {$requested eq "path-distribution" && $name eq "path-csv"} { return 1 }
    return 0
}

proc normalize_report_stage {stage} {
    switch -- $stage {
        "auto" { return "auto" }
        "post-synthesis" - "post_synthesis" - "synthesis" - "synth" { return "post-synthesis" }
        "post-implementation" - "post_implementation" - "implementation" - "impl" { return "post-implementation" }
        default { error "Invalid report_stage '$stage'. Use auto, post-synthesis, or post-implementation." }
    }
}

proc synthesize_current_design {} {
    set srcset [get_filesets sources_1]
    set top [get_property top $srcset]
    set part [get_property part [current_project]]
    puts "Synthesizing top=$top part=$part"

    update_compile_order -fileset sources_1
    synth_design -top $top -part $part
}

proc normalize_boolean {value} {
    set normalized [string tolower $value]
    switch -- $normalized {
        "1" - "true" - "yes" - "y" { return 1 }
        "0" - "false" - "no" - "n" - "" { return 0 }
        default { error "Invalid boolean value '$value'. Use 0/1, true/false, or yes/no." }
    }
}

proc implement_current_design {} {
    puts "Running in-memory post-implementation flow..."
    synthesize_current_design
    puts "Optimizing design..."
    opt_design
    puts "Placing design..."
    place_design
    puts "Routing design..."
    route_design
}

set requested_stage [normalize_report_stage $requested_stage]
set run_implementation [normalize_boolean $run_implementation]

open_project $project_xpr

set report_stage ""

# Stage selection:
#   auto                 preserves the historical behavior: use impl_1 when it is
#                        openable, otherwise synthesize and report post-synthesis.
#   post-synthesis       always synthesizes the current project sources and reports
#                        that netlist.
#   post-implementation  opens an implemented impl_1 run. When report.sh passes
#                        run_implementation=1 (currently --create-projects with
#                        --stage post-implementation), run synth/opt/place/route
#                        in memory if impl_1 is not openable yet.
if {$requested_stage eq "post-synthesis"} {
    puts "Generating explicitly requested post-synthesis reports."
    synthesize_current_design
    set report_stage "post_synthesis"
} elseif {$requested_stage eq "post-implementation"} {
    if {[catch {open_run impl_1} err]} {
        if {$run_implementation} {
            puts "Implementation run impl_1 is not openable; running in-memory implementation because run_impl=1."
            puts "Original open_run message:"
            puts $err
            implement_current_design
        } else {
            puts "ERROR: Could not open implementation run impl_1."
            puts "Run implementation first, or retry with --create-projects --stage post-implementation to let report.sh run it."
            puts "Original error:"
            puts $err
            error "Cannot export post-implementation reports without implemented design"
        }
    }
    set report_stage "post_implementation"
} else {
    if {[catch {open_run impl_1} err]} {
        puts "Implementation run impl_1 is not openable; generating post-synthesis reports instead."
        puts "Original open_run message:"
        puts $err

        synthesize_current_design
        set report_stage "post_synthesis"
    } else {
        set report_stage "post_implementation"
    }
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
puts $fp "report_stage=$report_stage"
puts $fp "project_xpr=$project_xpr"
puts $fp "repo_root=$repo_root"
puts $fp "vivado_version=[version]"
puts $fp "date=[clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"

if {[file exists [file join $repo_root ".git"]]} {
    if {![catch {exec git -C $repo_root rev-parse HEAD} git_hash]} {
        puts $fp "repo_commit=$git_hash"
    }

    if {![catch {exec git -C [file join $repo_root "cv32e40p_baseline"] rev-parse HEAD} baseline_hash]} {
        puts $fp "cv32e40p_baseline_commit=$baseline_hash"
    }

    if {![catch {exec git -C [file join $repo_root "cv32e40p_no_mul_forwarding"] rev-parse HEAD} modified_hash]} {
        puts $fp "cv32e40p_no_mul_forwarding_commit=$modified_hash"
    }

    if {![catch {exec git -C [file join $repo_root "cv32e40p_no_alu_forwarding"] rev-parse HEAD} no_alu_hash]} {
        puts $fp "cv32e40p_no_alu_forwarding_commit=$no_alu_hash"
    }
}

close $fp

puts "========================================"
puts "Report export complete"
puts "Output directory:"
puts "  $report_dir"
puts "========================================"

close_project