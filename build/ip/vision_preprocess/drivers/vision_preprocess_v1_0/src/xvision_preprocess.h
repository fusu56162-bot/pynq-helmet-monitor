// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
// Tool Version Limit: 2026.06
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
#ifndef XVISION_PREPROCESS_H
#define XVISION_PREPROCESS_H

#ifdef __cplusplus
extern "C" {
#endif

/***************************** Include Files *********************************/
#ifndef __linux__
#include "xil_types.h"
#include "xil_assert.h"
#include "xstatus.h"
#include "xil_io.h"
#else
#include <stdint.h>
#include <assert.h>
#include <dirent.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stddef.h>
#endif
#include "xvision_preprocess_hw.h"

/**************************** Type Definitions ******************************/
#ifdef __linux__
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
#else
typedef struct {
#ifdef SDT
    char *Name;
#else
    u16 DeviceId;
#endif
    u64 Control_BaseAddress;
} XVision_preprocess_Config;
#endif

typedef struct {
    u64 Control_BaseAddress;
    u32 IsReady;
} XVision_preprocess;

typedef u32 word_type;

/***************** Macros (Inline Functions) Definitions *********************/
#ifndef __linux__
#define XVision_preprocess_WriteReg(BaseAddress, RegOffset, Data) \
    Xil_Out32((BaseAddress) + (RegOffset), (u32)(Data))
#define XVision_preprocess_ReadReg(BaseAddress, RegOffset) \
    Xil_In32((BaseAddress) + (RegOffset))
#else
#define XVision_preprocess_WriteReg(BaseAddress, RegOffset, Data) \
    *(volatile u32*)((BaseAddress) + (RegOffset)) = (u32)(Data)
#define XVision_preprocess_ReadReg(BaseAddress, RegOffset) \
    *(volatile u32*)((BaseAddress) + (RegOffset))

#define Xil_AssertVoid(expr)    assert(expr)
#define Xil_AssertNonvoid(expr) assert(expr)

#define XST_SUCCESS             0
#define XST_DEVICE_NOT_FOUND    2
#define XST_OPEN_DEVICE_FAILED  3
#define XIL_COMPONENT_IS_READY  1
#endif

/************************** Function Prototypes *****************************/
#ifndef __linux__
#ifdef SDT
int XVision_preprocess_Initialize(XVision_preprocess *InstancePtr, UINTPTR BaseAddress);
XVision_preprocess_Config* XVision_preprocess_LookupConfig(UINTPTR BaseAddress);
#else
int XVision_preprocess_Initialize(XVision_preprocess *InstancePtr, u16 DeviceId);
XVision_preprocess_Config* XVision_preprocess_LookupConfig(u16 DeviceId);
#endif
int XVision_preprocess_CfgInitialize(XVision_preprocess *InstancePtr, XVision_preprocess_Config *ConfigPtr);
#else
int XVision_preprocess_Initialize(XVision_preprocess *InstancePtr, const char* InstanceName);
int XVision_preprocess_Release(XVision_preprocess *InstancePtr);
#endif

void XVision_preprocess_Start(XVision_preprocess *InstancePtr);
u32 XVision_preprocess_IsDone(XVision_preprocess *InstancePtr);
u32 XVision_preprocess_IsIdle(XVision_preprocess *InstancePtr);
u32 XVision_preprocess_IsReady(XVision_preprocess *InstancePtr);
void XVision_preprocess_EnableAutoRestart(XVision_preprocess *InstancePtr);
void XVision_preprocess_DisableAutoRestart(XVision_preprocess *InstancePtr);


void XVision_preprocess_InterruptGlobalEnable(XVision_preprocess *InstancePtr);
void XVision_preprocess_InterruptGlobalDisable(XVision_preprocess *InstancePtr);
void XVision_preprocess_InterruptEnable(XVision_preprocess *InstancePtr, u32 Mask);
void XVision_preprocess_InterruptDisable(XVision_preprocess *InstancePtr, u32 Mask);
void XVision_preprocess_InterruptClear(XVision_preprocess *InstancePtr, u32 Mask);
u32 XVision_preprocess_InterruptGetEnabled(XVision_preprocess *InstancePtr);
u32 XVision_preprocess_InterruptGetStatus(XVision_preprocess *InstancePtr);

#ifdef __cplusplus
}
#endif

#endif
