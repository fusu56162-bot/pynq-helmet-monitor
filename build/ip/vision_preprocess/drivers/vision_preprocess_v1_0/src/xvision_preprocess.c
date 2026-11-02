// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
// Tool Version Limit: 2026.06
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
/***************************** Include Files *********************************/
#include "xvision_preprocess.h"

/************************** Function Implementation *************************/
#ifndef __linux__
int XVision_preprocess_CfgInitialize(XVision_preprocess *InstancePtr, XVision_preprocess_Config *ConfigPtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(ConfigPtr != NULL);

    InstancePtr->Control_BaseAddress = ConfigPtr->Control_BaseAddress;
    InstancePtr->IsReady = XIL_COMPONENT_IS_READY;

    return XST_SUCCESS;
}
#endif

void XVision_preprocess_Start(XVision_preprocess *InstancePtr) {
    u32 Data;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XVision_preprocess_ReadReg(InstancePtr->Control_BaseAddress, XVISION_PREPROCESS_CONTROL_ADDR_AP_CTRL) & 0x80;
    XVision_preprocess_WriteReg(InstancePtr->Control_BaseAddress, XVISION_PREPROCESS_CONTROL_ADDR_AP_CTRL, Data | 0x01);
}

u32 XVision_preprocess_IsDone(XVision_preprocess *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XVision_preprocess_ReadReg(InstancePtr->Control_BaseAddress, XVISION_PREPROCESS_CONTROL_ADDR_AP_CTRL);
    return (Data >> 1) & 0x1;
}

u32 XVision_preprocess_IsIdle(XVision_preprocess *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XVision_preprocess_ReadReg(InstancePtr->Control_BaseAddress, XVISION_PREPROCESS_CONTROL_ADDR_AP_CTRL);
    return (Data >> 2) & 0x1;
}

u32 XVision_preprocess_IsReady(XVision_preprocess *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XVision_preprocess_ReadReg(InstancePtr->Control_BaseAddress, XVISION_PREPROCESS_CONTROL_ADDR_AP_CTRL);
    // check ap_start to see if the pcore is ready for next input
    return !(Data & 0x1);
}

void XVision_preprocess_EnableAutoRestart(XVision_preprocess *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XVision_preprocess_WriteReg(InstancePtr->Control_BaseAddress, XVISION_PREPROCESS_CONTROL_ADDR_AP_CTRL, 0x80);
}

void XVision_preprocess_DisableAutoRestart(XVision_preprocess *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XVision_preprocess_WriteReg(InstancePtr->Control_BaseAddress, XVISION_PREPROCESS_CONTROL_ADDR_AP_CTRL, 0);
}

void XVision_preprocess_InterruptGlobalEnable(XVision_preprocess *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XVision_preprocess_WriteReg(InstancePtr->Control_BaseAddress, XVISION_PREPROCESS_CONTROL_ADDR_GIE, 1);
}

void XVision_preprocess_InterruptGlobalDisable(XVision_preprocess *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XVision_preprocess_WriteReg(InstancePtr->Control_BaseAddress, XVISION_PREPROCESS_CONTROL_ADDR_GIE, 0);
}

void XVision_preprocess_InterruptEnable(XVision_preprocess *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XVision_preprocess_ReadReg(InstancePtr->Control_BaseAddress, XVISION_PREPROCESS_CONTROL_ADDR_IER);
    XVision_preprocess_WriteReg(InstancePtr->Control_BaseAddress, XVISION_PREPROCESS_CONTROL_ADDR_IER, Register | Mask);
}

void XVision_preprocess_InterruptDisable(XVision_preprocess *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XVision_preprocess_ReadReg(InstancePtr->Control_BaseAddress, XVISION_PREPROCESS_CONTROL_ADDR_IER);
    XVision_preprocess_WriteReg(InstancePtr->Control_BaseAddress, XVISION_PREPROCESS_CONTROL_ADDR_IER, Register & (~Mask));
}

void XVision_preprocess_InterruptClear(XVision_preprocess *InstancePtr, u32 Mask) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XVision_preprocess_WriteReg(InstancePtr->Control_BaseAddress, XVISION_PREPROCESS_CONTROL_ADDR_ISR, Mask);
}

u32 XVision_preprocess_InterruptGetEnabled(XVision_preprocess *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XVision_preprocess_ReadReg(InstancePtr->Control_BaseAddress, XVISION_PREPROCESS_CONTROL_ADDR_IER);
}

u32 XVision_preprocess_InterruptGetStatus(XVision_preprocess *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XVision_preprocess_ReadReg(InstancePtr->Control_BaseAddress, XVISION_PREPROCESS_CONTROL_ADDR_ISR);
}

