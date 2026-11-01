// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
// Tool Version Limit: 2026.06
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
#ifndef __linux__

#include "xstatus.h"
#ifdef SDT
#include "xparameters.h"
#endif
#include "xchain_float.h"

extern XChain_float_Config XChain_float_ConfigTable[];

#ifdef SDT
XChain_float_Config *XChain_float_LookupConfig(UINTPTR BaseAddress) {
	XChain_float_Config *ConfigPtr = NULL;

	int Index;

	for (Index = (u32)0x0; XChain_float_ConfigTable[Index].Name != NULL; Index++) {
		if (!BaseAddress || XChain_float_ConfigTable[Index].Control_BaseAddress == BaseAddress) {
			ConfigPtr = &XChain_float_ConfigTable[Index];
			break;
		}
	}

	return ConfigPtr;
}

int XChain_float_Initialize(XChain_float *InstancePtr, UINTPTR BaseAddress) {
	XChain_float_Config *ConfigPtr;

	Xil_AssertNonvoid(InstancePtr != NULL);

	ConfigPtr = XChain_float_LookupConfig(BaseAddress);
	if (ConfigPtr == NULL) {
		InstancePtr->IsReady = 0;
		return (XST_DEVICE_NOT_FOUND);
	}

	return XChain_float_CfgInitialize(InstancePtr, ConfigPtr);
}
#else
XChain_float_Config *XChain_float_LookupConfig(u16 DeviceId) {
	XChain_float_Config *ConfigPtr = NULL;

	int Index;

	for (Index = 0; Index < XPAR_XCHAIN_FLOAT_NUM_INSTANCES; Index++) {
		if (XChain_float_ConfigTable[Index].DeviceId == DeviceId) {
			ConfigPtr = &XChain_float_ConfigTable[Index];
			break;
		}
	}

	return ConfigPtr;
}

int XChain_float_Initialize(XChain_float *InstancePtr, u16 DeviceId) {
	XChain_float_Config *ConfigPtr;

	Xil_AssertNonvoid(InstancePtr != NULL);

	ConfigPtr = XChain_float_LookupConfig(DeviceId);
	if (ConfigPtr == NULL) {
		InstancePtr->IsReady = 0;
		return (XST_DEVICE_NOT_FOUND);
	}

	return XChain_float_CfgInitialize(InstancePtr, ConfigPtr);
}
#endif

#endif

