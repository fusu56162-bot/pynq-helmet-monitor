// Segment boundaries ONLY. No convolution, dequantization, activation or
// requantization is moved back to ARM. Both copies must be timed per frame.
#include <stdint.h>
#include <stddef.h>
#include <cstring>
#include "generated/input_normalization_bits.h"
#ifdef _WIN32
#define BRIDGE_EXPORT __declspec(dllexport)
#else
#define BRIDGE_EXPORT
#endif
static bool overlap(const void* a, size_t as, const void* b, size_t bs) {
    uintptr_t ap = reinterpret_cast<uintptr_t>(a), bp = reinterpret_cast<uintptr_t>(b);
    if (ap > UINTPTR_MAX-as || bp > UINTPTR_MAX-bs) return true;
    return ap < bp+bs && bp < ap+as;
}

// Only accepted if every normalized float is EXACTLY an original captured
// byte-level normalization value. Non-byte inputs are rejected, never rounded
// silently into a different model input. Caller must not start DMA on error.
extern "C" BRIDGE_EXPORT int chain_boundary_pack_input(
    const float* chw, size_t count, uint8_t* rgb, size_t capacity, int width, int height) {
    if (!chw || !rgb || width < 1 || height < 1 || width > 112 || height > 112) return -1;
    const size_t plane = size_t(width)*height*4, elements = plane*3;
    if (count != elements || capacity != elements) return -1;
    if (overlap(chw, count*4, rgb, capacity)) return -3;
    for (size_t p = 0; p < plane; ++p) {
        for (int c = 0; c < 3; ++c) {
            const float value = chw[size_t(c)*plane+p];
            // This rejects NaN/infinity before any float-to-integer conversion.
            if (!(value >= 0.f && value <= 1.f)) return -2;
            unsigned byte = unsigned(value*255.f+0.5f);
            uint32_t actual;
            std::memcpy(&actual, &value, sizeof(actual));
            if (byte > 255 || actual != INPUT_NORMALIZATION_BITS[byte]) return -2;
            rgb[p*3+c] = uint8_t(byte);
        }
    }
    return 0;
}

// ncnn packed4 = [channel_group][pixel][4 lanes], NOT HWC32.
// Caller supplies owned, contiguous ncnn allocation: Mat(w,h,8,16u,4), whose
// cstep equals w*h for this float32 pack4 element size. Never wrap arbitrary
// HWC bytes as a packed4 Mat; never free or reuse live DMA memory prematurely.
extern "C" BRIDGE_EXPORT int chain_boundary_hwc_to_packed4(
    const uint32_t* hwc, size_t count, uint32_t* packed, size_t capacity, int width, int height) {
    if (!hwc || !packed || width < 1 || height < 1 || width > 56 || height > 56) return -1;
    const size_t plane = size_t(width)*height, elements = plane*32;
    if (count != elements || capacity != elements) return -1;
    if (overlap(hwc, count*4, packed, capacity*4)) return -3;
    for (int group = 0; group < 8; ++group)
        for (size_t p = 0; p < plane; ++p)
            std::memcpy(packed+(size_t(group)*plane+p)*4, hwc+p*32+group*4, 16);
    return 0;
}
