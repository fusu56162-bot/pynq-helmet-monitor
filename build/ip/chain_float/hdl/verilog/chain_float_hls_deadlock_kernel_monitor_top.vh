
wire kernel_monitor_reset;
wire kernel_monitor_clock;
wire kernel_monitor_report;
assign kernel_monitor_reset = ~ap_rst_n;
assign kernel_monitor_clock = ap_clk;
assign kernel_monitor_report = 1'b0;
wire [1:0] axis_block_sigs;
wire [10:0] inst_idle_sigs;
wire [4:0] inst_block_sigs;
wire kernel_block;

assign axis_block_sigs[0] = ~grp_pipeline_fu_497.reorg_quantize_U0.grp_reorg_quantize_Pipeline_LOAD_PAIR_VITIS_LOOP_18_1_fu_122.src_TDATA_blk_n;
assign axis_block_sigs[1] = ~grp_pipeline_fu_497.serialize_U0.grp_serialize_Pipeline_VITIS_LOOP_187_1_VITIS_LOOP_190_2_fu_140.dst_TDATA_blk_n;

assign inst_idle_sigs[0] = grp_pipeline_fu_497.reorg_quantize_U0.ap_idle;
assign inst_block_sigs[0] = (grp_pipeline_fu_497.reorg_quantize_U0.ap_done & ~grp_pipeline_fu_497.reorg_quantize_U0.ap_continue) | ~grp_pipeline_fu_497.reorg_quantize_U0.grp_reorg_quantize_Pipeline_REORG_PIXELS_REORG_CHANNELS_fu_142.pixels0_blk_n;
assign inst_idle_sigs[1] = grp_pipeline_fu_497.first_convolution_U0.ap_idle;
assign inst_block_sigs[1] = (grp_pipeline_fu_497.first_convolution_U0.ap_done & ~grp_pipeline_fu_497.first_convolution_U0.ap_continue) | ~grp_pipeline_fu_497.first_convolution_U0.grp_convolve_12_16_1_96_12_s_fu_242.pixels0_blk_n | ~grp_pipeline_fu_497.first_convolution_U0.grp_convolve_12_16_1_96_12_s_fu_242.grp_convolve_Pipeline_OUTPUT_COLUMNS_KERNEL_Y_KERNEL_X_INPUT_GROUPS_fu_399.sums0_blk_n;
assign inst_idle_sigs[2] = grp_pipeline_fu_497.activate_quantize_U0.ap_idle;
assign inst_block_sigs[2] = (grp_pipeline_fu_497.activate_quantize_U0.ap_done & ~grp_pipeline_fu_497.activate_quantize_U0.ap_continue) | ~grp_pipeline_fu_497.activate_quantize_U0.grp_activate_quantize_Pipeline_ACTIVATE_PIXELS_ACTIVATE_CHANNELS_fu_99.sums0_blk_n | ~grp_pipeline_fu_497.activate_quantize_U0.grp_activate_quantize_Pipeline_ACTIVATE_PIXELS_ACTIVATE_CHANNELS_fu_99.pixels1_blk_n | ~grp_pipeline_fu_497.activate_quantize_U0.errors_blk_n;
assign inst_idle_sigs[3] = grp_pipeline_fu_497.second_convolution_U0.ap_idle;
assign inst_block_sigs[3] = (grp_pipeline_fu_497.second_convolution_U0.ap_done & ~grp_pipeline_fu_497.second_convolution_U0.ap_continue) | ~grp_pipeline_fu_497.second_convolution_U0.grp_convolve_16_32_2_128_18_s_fu_242.pixels1_blk_n | ~grp_pipeline_fu_497.second_convolution_U0.grp_convolve_16_32_2_128_18_s_fu_242.grp_convolve_Pipeline_OUTPUT_COLUMNS_OUTPUT_GROUPS_KERNEL_Y_KERNEL_X_INPUT_GROUPS_fu_437.sums1_blk_n;
assign inst_idle_sigs[4] = grp_pipeline_fu_497.serialize_U0.ap_idle;
assign inst_block_sigs[4] = (grp_pipeline_fu_497.serialize_U0.ap_done & ~grp_pipeline_fu_497.serialize_U0.ap_continue) | ~grp_pipeline_fu_497.serialize_U0.grp_serialize_Pipeline_VITIS_LOOP_187_1_VITIS_LOOP_190_2_fu_140.sums1_blk_n | ~grp_pipeline_fu_497.serialize_U0.errors_blk_n;

assign inst_idle_sigs[5] = 1'b0;
assign inst_idle_sigs[6] = grp_pipeline_fu_497.ap_idle;
assign inst_idle_sigs[7] = grp_pipeline_fu_497.reorg_quantize_U0.ap_idle;
assign inst_idle_sigs[8] = grp_pipeline_fu_497.reorg_quantize_U0.grp_reorg_quantize_Pipeline_LOAD_PAIR_VITIS_LOOP_18_1_fu_122.ap_idle;
assign inst_idle_sigs[9] = grp_pipeline_fu_497.serialize_U0.ap_idle;
assign inst_idle_sigs[10] = grp_pipeline_fu_497.serialize_U0.grp_serialize_Pipeline_VITIS_LOOP_187_1_VITIS_LOOP_190_2_fu_140.ap_idle;

chain_float_hls_deadlock_idx0_monitor chain_float_hls_deadlock_idx0_monitor_U (
    .clock(kernel_monitor_clock),
    .reset(kernel_monitor_reset),
    .axis_block_sigs(axis_block_sigs),
    .inst_idle_sigs(inst_idle_sigs),
    .inst_block_sigs(inst_block_sigs),
    .block(kernel_block)
);


always @ (kernel_block or kernel_monitor_reset) begin
    if (kernel_block == 1'b1 && kernel_monitor_reset == 1'b0) begin
        find_kernel_block = 1'b1;
    end
    else begin
        find_kernel_block = 1'b0;
    end
end
