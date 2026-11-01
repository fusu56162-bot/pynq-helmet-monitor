// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
// Tool Version Limit: 2026.06
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
#ifndef XCHAIN_FLOAT_H
#define XCHAIN_FLOAT_H

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
#include "xchain_float_hw.h"

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
} XChain_float_Config;
#endif

typedef struct {
    u64 Control_BaseAddress;
    u32 IsReady;
} XChain_float;

typedef u32 word_type;

/***************** Macros (Inline Functions) Definitions *********************/
#ifndef __linux__
#define XChain_float_WriteReg(BaseAddress, RegOffset, Data) \
    Xil_Out32((BaseAddress) + (RegOffset), (u32)(Data))
#define XChain_float_ReadReg(BaseAddress, RegOffset) \
    Xil_In32((BaseAddress) + (RegOffset))
#else
#define XChain_float_WriteReg(BaseAddress, RegOffset, Data) \
    *(volatile u32*)((BaseAddress) + (RegOffset)) = (u32)(Data)
#define XChain_float_ReadReg(BaseAddress, RegOffset) \
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
int XChain_float_Initialize(XChain_float *InstancePtr, UINTPTR BaseAddress);
XChain_float_Config* XChain_float_LookupConfig(UINTPTR BaseAddress);
#else
int XChain_float_Initialize(XChain_float *InstancePtr, u16 DeviceId);
XChain_float_Config* XChain_float_LookupConfig(u16 DeviceId);
#endif
int XChain_float_CfgInitialize(XChain_float *InstancePtr, XChain_float_Config *ConfigPtr);
#else
int XChain_float_Initialize(XChain_float *InstancePtr, const char* InstanceName);
int XChain_float_Release(XChain_float *InstancePtr);
#endif

void XChain_float_Start(XChain_float *InstancePtr);
u32 XChain_float_IsDone(XChain_float *InstancePtr);
u32 XChain_float_IsIdle(XChain_float *InstancePtr);
u32 XChain_float_IsReady(XChain_float *InstancePtr);
void XChain_float_EnableAutoRestart(XChain_float *InstancePtr);
void XChain_float_DisableAutoRestart(XChain_float *InstancePtr);

void XChain_float_Set_width(XChain_float *InstancePtr, u32 Data);
u32 XChain_float_Get_width(XChain_float *InstancePtr);
void XChain_float_Set_height(XChain_float *InstancePtr, u32 Data);
u32 XChain_float_Get_height(XChain_float *InstancePtr);
u32 XChain_float_Get_status(XChain_float *InstancePtr);
u32 XChain_float_Get_status_vld(XChain_float *InstancePtr);

void XChain_float_InterruptGlobalEnable(XChain_float *InstancePtr);
void XChain_float_InterruptGlobalDisable(XChain_float *InstancePtr);
void XChain_float_InterruptEnable(XChain_float *InstancePtr, u32 Mask);
void XChain_float_InterruptDisable(XChain_float *InstancePtr, u32 Mask);
void XChain_float_InterruptClear(XChain_float *InstancePtr, u32 Mask);
u32 XChain_float_InterruptGetEnabled(XChain_float *InstancePtr);
u32 XChain_float_InterruptGetStatus(XChain_float *InstancePtr);

#ifdef __cplusplus
}
#endif

#endif
