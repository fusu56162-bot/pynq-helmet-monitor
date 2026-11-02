// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
// Tool Version Limit: 2026.06
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
/***************************** Include Files *********************************/
#include "xchain_float.h"

/************************** Function Implementation *************************/
#ifndef __linux__
int XChain_float_CfgInitialize(XChain_float *InstancePtr, XChain_float_Config *ConfigPtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(ConfigPtr != NULL);

    InstancePtr->Control_BaseAddress = ConfigPtr->Control_BaseAddress;
    InstancePtr->IsReady = XIL_COMPONENT_IS_READY;

    return XST_SUCCESS;
}
#endif

void XChain_float_Start(XChain_float *InstancePtr) {
    u32 Data;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChain_float_ReadReg(InstancePtr->Control_BaseAddress, XCHAIN_FLOAT_CONTROL_ADDR_AP_CTRL) & 0x80;
    XChain_float_WriteReg(InstancePtr->Control_BaseAddress, XCHAIN_FLOAT_CONTROL_ADDR_AP_CTRL, Data | 0x01);
}

u32 XChain_float_IsDone(XChain_float *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChain_float_ReadReg(InstancePtr->Control_BaseAddress, XCHAIN_FLOAT_CONTROL_ADDR_AP_CTRL);
    return (Data >> 1) & 0x1;
}

u32 XChain_float_IsIdle(XChain_float *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChain_float_ReadReg(InstancePtr->Control_BaseAddress, XCHAIN_FLOAT_CONTROL_ADDR_AP_CTRL);
    return (Data >> 2) & 0x1;
}

u32 XChain_float_IsReady(XChain_float *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChain_float_ReadReg(InstancePtr->Control_BaseAddress, XCHAIN_FLOAT_CONTROL_ADDR_AP_CTRL);
    // check ap_start to see if the pcore is ready for next input
    return !(Data & 0x1);
}

void XChain_float_EnableAutoRestart(XChain_float *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChain_float_WriteReg(InstancePtr->Control_BaseAddress, XCHAIN_FLOAT_CONTROL_ADDR_AP_CTRL, 0x80);
}

void XChain_float_DisableAutoRestart(XChain_float *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChain_float_WriteReg(InstancePtr->Control_BaseAddress, XCHAIN_FLOAT_CONTROL_ADDR_AP_CTRL, 0);
}

void XChain_float_Set_width(XChain_float *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChain_float_WriteReg(InstancePtr->Control_BaseAddress, XCHAIN_FLOAT_CONTROL_ADDR_WIDTH_DATA, Data);
}

u32 XChain_float_Get_width(XChain_float *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChain_float_ReadReg(InstancePtr->Control_BaseAddress, XCHAIN_FLOAT_CONTROL_ADDR_WIDTH_DATA);
    return Data;
}

void XChain_float_Set_height(XChain_float *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChain_float_WriteReg(InstancePtr->Control_BaseAddress, XCHAIN_FLOAT_CONTROL_ADDR_HEIGHT_DATA, Data);
}

u32 XChain_float_Get_height(XChain_float *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChain_float_ReadReg(InstancePtr->Control_BaseAddress, XCHAIN_FLOAT_CONTROL_ADDR_HEIGHT_DATA);
    return Data;
}

u32 XChain_float_Get_status(XChain_float *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChain_float_ReadReg(InstancePtr->Control_BaseAddress, XCHAIN_FLOAT_CONTROL_ADDR_STATUS_DATA);
    return Data;
}

u32 XChain_float_Get_status_vld(XChain_float *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChain_float_ReadReg(InstancePtr->Control_BaseAddress, XCHAIN_FLOAT_CONTROL_ADDR_STATUS_CTRL);
    return Data & 0x1;
}

void XChain_float_InterruptGlobalEnable(XChain_float *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChain_float_WriteReg(InstancePtr->Control_BaseAddress, XCHAIN_FLOAT_CONTROL_ADDR_GIE, 1);
}

void XChain_float_InterruptGlobalDisable(XChain_float *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChain_float_WriteReg(InstancePtr->Control_BaseAddress, XCHAIN_FLOAT_CONTROL_ADDR_GIE, 0);
}

void XChain_float_InterruptEnable(XChain_float *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XChain_float_ReadReg(InstancePtr->Control_BaseAddress, XCHAIN_FLOAT_CONTROL_ADDR_IER);
    XChain_float_WriteReg(InstancePtr->Control_BaseAddress, XCHAIN_FLOAT_CONTROL_ADDR_IER, Register | Mask);
}

void XChain_float_InterruptDisable(XChain_float *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XChain_float_ReadReg(InstancePtr->Control_BaseAddress, XCHAIN_FLOAT_CONTROL_ADDR_IER);
    XChain_float_WriteReg(InstancePtr->Control_BaseAddress, XCHAIN_FLOAT_CONTROL_ADDR_IER, Register & (~Mask));
}

void XChain_float_InterruptClear(XChain_float *InstancePtr, u32 Mask) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChain_float_WriteReg(InstancePtr->Control_BaseAddress, XCHAIN_FLOAT_CONTROL_ADDR_ISR, Mask);
}

u32 XChain_float_InterruptGetEnabled(XChain_float *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XChain_float_ReadReg(InstancePtr->Control_BaseAddress, XCHAIN_FLOAT_CONTROL_ADDR_IER);
}

u32 XChain_float_InterruptGetStatus(XChain_float *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XChain_float_ReadReg(InstancePtr->Control_BaseAddress, XCHAIN_FLOAT_CONTROL_ADDR_ISR);
}

