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
#include "xvision_preprocess.h"

extern XVision_preprocess_Config XVision_preprocess_ConfigTable[];

#ifdef SDT
XVision_preprocess_Config *XVision_preprocess_LookupConfig(UINTPTR BaseAddress) {
	XVision_preprocess_Config *ConfigPtr = NULL;

	int Index;

	for (Index = (u32)0x0; XVision_preprocess_ConfigTable[Index].Name != NULL; Index++) {
		if (!BaseAddress || XVision_preprocess_ConfigTable[Index].Control_BaseAddress == BaseAddress) {
			ConfigPtr = &XVision_preprocess_ConfigTable[Index];
			break;
		}
	}

	return ConfigPtr;
}

int XVision_preprocess_Initialize(XVision_preprocess *InstancePtr, UINTPTR BaseAddress) {
	XVision_preprocess_Config *ConfigPtr;

	Xil_AssertNonvoid(InstancePtr != NULL);

	ConfigPtr = XVision_preprocess_LookupConfig(BaseAddress);
	if (ConfigPtr == NULL) {
		InstancePtr->IsReady = 0;
		return (XST_DEVICE_NOT_FOUND);
	}

	return XVision_preprocess_CfgInitialize(InstancePtr, ConfigPtr);
}
#else
XVision_preprocess_Config *XVision_preprocess_LookupConfig(u16 DeviceId) {
	XVision_preprocess_Config *ConfigPtr = NULL;

	int Index;

	for (Index = 0; Index < XPAR_XVISION_PREPROCESS_NUM_INSTANCES; Index++) {
		if (XVision_preprocess_ConfigTable[Index].DeviceId == DeviceId) {
			ConfigPtr = &XVision_preprocess_ConfigTable[Index];
			break;
		}
	}

	return ConfigPtr;
}

int XVision_preprocess_Initialize(XVision_preprocess *InstancePtr, u16 DeviceId) {
	XVision_preprocess_Config *ConfigPtr;

	Xil_AssertNonvoid(InstancePtr != NULL);

	ConfigPtr = XVision_preprocess_LookupConfig(DeviceId);
	if (ConfigPtr == NULL) {
		InstancePtr->IsReady = 0;
		return (XST_DEVICE_NOT_FOUND);
	}

	return XVision_preprocess_CfgInitialize(InstancePtr, ConfigPtr);
}
#endif

#endif

