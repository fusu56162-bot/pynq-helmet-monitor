
wire kernel_monitor_reset;
wire kernel_monitor_clock;
wire kernel_monitor_report;
assign kernel_monitor_reset = ~ap_rst_n;
assign kernel_monitor_clock = ap_clk;
assign kernel_monitor_report = 1'b0;
wire [3:0] axis_block_sigs;
wire [3:0] inst_idle_sigs;
wire [0:0] inst_block_sigs;
wire kernel_block;

assign axis_block_sigs[0] = ~grp_vision_preprocess_Pipeline_VITIS_LOOP_35_1_VITIS_LOOP_36_2_fu_64.dst_TDATA_blk_n;
assign axis_block_sigs[1] = ~grp_vision_preprocess_Pipeline_VITIS_LOOP_43_3_VITIS_LOOP_44_4_fu_82.src_TDATA_blk_n;
assign axis_block_sigs[2] = ~grp_vision_preprocess_Pipeline_VITIS_LOOP_43_3_VITIS_LOOP_44_4_fu_82.dst_TDATA_blk_n;
assign axis_block_sigs[3] = ~grp_vision_preprocess_Pipeline_VITIS_LOOP_58_5_VITIS_LOOP_59_6_fu_114.dst_TDATA_blk_n;

assign inst_block_sigs[0] = 1'b0;

assign inst_idle_sigs[0] = 1'b0;
assign inst_idle_sigs[1] = grp_vision_preprocess_Pipeline_VITIS_LOOP_35_1_VITIS_LOOP_36_2_fu_64.ap_idle;
assign inst_idle_sigs[2] = grp_vision_preprocess_Pipeline_VITIS_LOOP_43_3_VITIS_LOOP_44_4_fu_82.ap_idle;
assign inst_idle_sigs[3] = grp_vision_preprocess_Pipeline_VITIS_LOOP_58_5_VITIS_LOOP_59_6_fu_114.ap_idle;

vision_preprocess_hls_deadlock_idx0_monitor vision_preprocess_hls_deadlock_idx0_monitor_U (
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
