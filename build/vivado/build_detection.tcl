# Detection-only source integration. Does not open an existing project or board.
set root [file normalize [file join [file dirname [info script]] ..]]
set phase create_only
if {[llength $argv]} {set phase [lindex $argv 0]}
if {$phase ni {create_only full}} {error "Use create_only or full"}
set dest [file join $root build_detection]
if {[file exists $dest]} {error "Choose an empty output folder; existing project preserved"}
create_project rider_monitor $dest -part xc7z020clg400-1
set_property BOARD_PART tul.com.tw:pynq-z2:part0:1.0 [current_project]
set_property IP_REPO_PATHS [list $root/ip/chain_float $root/ip/vision_preprocess] [current_project]
update_ip_catalog
source $root/vivado/connected_detection.tcl
validate_bd_design -force
save_bd_design
set bd [get_files -filter {FILE_TYPE == "Block Designs"}]
generate_target all $bd
set wrappers [make_wrapper -files $bd -top]
add_files -norecurse $wrappers
set_property top rider_monitor_wrapper [current_fileset]
update_compile_order -fileset sources_1
if {$phase eq "full"} {
    launch_runs synth_1 -jobs 4
    wait_on_run synth_1
    if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Synthesis failed"}
    launch_runs impl_1 -to_step route_design -jobs 4
    wait_on_run impl_1
    if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "Routing failed"}
    open_run impl_1
    report_utilization -file $root/build_detection/utilization.rpt
    report_timing_summary -file $root/build_detection/timing.rpt
    report_drc -file $root/build_detection/drc.rpt
    # A new integration is not an automatic release. Inspect all reports first.
    close_design
}
close_project
puts "SOURCE_INTEGRATION_COMPLETE_NOT_BOARD_VALIDATED"
exit 0
