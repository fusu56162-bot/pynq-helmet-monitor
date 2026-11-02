// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
// Tool Version Limit: 2026.06
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
// control
// 0x00 : Control signals
//        bit 0  - ap_start (Read/Write/COH)
//        bit 1  - ap_done (Read/COR)
//        bit 2  - ap_idle (Read)
//        bit 3  - ap_ready (Read/COR)
//        bit 7  - auto_restart (Read/Write)
//        bit 9  - interrupt (Read)
//        others - reserved
// 0x04 : Global Interrupt Enable Register
//        bit 0  - Global Interrupt Enable (Read/Write)
//        others - reserved
// 0x08 : IP Interrupt Enable Register (Read/Write)
//        bit 0 - enable ap_done interrupt (Read/Write)
//        bit 1 - enable ap_ready interrupt (Read/Write)
//        others - reserved
// 0x0c : IP Interrupt Status Register (Read/TOW)
//        bit 0 - ap_done (Read/TOW)
//        bit 1 - ap_ready (Read/TOW)
//        others - reserved
// 0x10 : Data signal of width
//        bit 31~0 - width[31:0] (Read/Write)
// 0x14 : reserved
// 0x18 : Data signal of height
//        bit 31~0 - height[31:0] (Read/Write)
// 0x1c : reserved
// 0x20 : Data signal of status
//        bit 31~0 - status[31:0] (Read)
// 0x24 : Control signal of status
//        bit 0  - status_ap_vld (Read/COR)
//        others - reserved
// (SC = Self Clear, COR = Clear on Read, TOW = Toggle on Write, COH = Clear on Handshake)

#define XCHAIN_FLOAT_CONTROL_ADDR_AP_CTRL     0x00
#define XCHAIN_FLOAT_CONTROL_ADDR_GIE         0x04
#define XCHAIN_FLOAT_CONTROL_ADDR_IER         0x08
#define XCHAIN_FLOAT_CONTROL_ADDR_ISR         0x0c
#define XCHAIN_FLOAT_CONTROL_ADDR_WIDTH_DATA  0x10
#define XCHAIN_FLOAT_CONTROL_BITS_WIDTH_DATA  32
#define XCHAIN_FLOAT_CONTROL_ADDR_HEIGHT_DATA 0x18
#define XCHAIN_FLOAT_CONTROL_BITS_HEIGHT_DATA 32
#define XCHAIN_FLOAT_CONTROL_ADDR_STATUS_DATA 0x20
#define XCHAIN_FLOAT_CONTROL_BITS_STATUS_DATA 32
#define XCHAIN_FLOAT_CONTROL_ADDR_STATUS_CTRL 0x24

