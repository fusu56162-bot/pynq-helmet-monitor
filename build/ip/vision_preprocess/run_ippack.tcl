# ==============================================================
# Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
# Tool Version Limit: 2026.06
# Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
# Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
# 
# ==============================================================
source -notrace "C:/AMDDesignTools/2026.1/Vitis/common/scripts/ipxhls.tcl"
set ip_out_dir "D:/Codex/fpga_work/conv_v1/hls/vision_preprocess/vision_preprocess/hls/impl/ip"
set data_file "D:/Codex/fpga_work/conv_v1/hls/vision_preprocess/vision_preprocess/hls/hls_data.json"
set src_dir [file dir $data_file]
set ip_types {vitis sysgen}
set ippack_opts_dict {}
if { [catch {::ipx::utils::package_hls_ip $ip_out_dir $data_file $ip_types $src_dir $ippack_opts_dict} res] } {
  puts "Caught error:\n$::errorInfo"
  error $res
}
