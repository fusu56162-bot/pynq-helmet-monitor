/* Altered scalar/HLS translation of ncnn/Cephes NEON exp, following the actual
 * pinned Cortex-A9 binary's (non-fused, reassociated) operation order.
 * This is NOT the original neon_mathfun.h and NOT a replacement ARM library.
 *
 * Original exp algorithm notice from neon_mathfun.h:
 * Copyright (C) 2011 Julien Pommier
 * This software is provided 'as-is', without any express or implied warranty.
 * In no event will the authors be held liable for any damages arising from
 * the use of this software.
 * Permission is granted to anyone to use this software for any purpose,
 * including commercial applications, and to alter it and redistribute it
 * freely, subject to the following restrictions:
 * 1. The origin of this software must not be misrepresented; you must not claim
 *    that you wrote the original software. If you use this software in a product,
 *    an acknowledgment in the product documentation would be appreciated but is
 *    not required.
 * 2. Altered source versions must be plainly marked as such, and must not be
 *    misrepresented as being the original software.
 * 3. This notice may not be removed or altered from any source distribution.
 */
#ifndef RIDER_TAIL_MATH_H
#define RIDER_TAIL_MATH_H
#include <stdint.h>
#include "generated/tail_constants.h"

union TailFloatBits { float f; uint32_t u; };

static uint32_t tail_bits(float f) {
#pragma HLS INLINE
    TailFloatBits v; v.f = f; return v.u;
}
static float tail_float(uint32_t u) {
#pragma HLS INLINE
    TailFloatBits v; v.u = u; return v.f;
}
static float tail_ftz(float x) {
#pragma HLS INLINE
    uint32_t u = tail_bits(x);
    if ((u & 0x7f800000u) == 0) u &= 0x80000000u;
    return tail_float(u);
}
static float tail_mul(float a, float b) {
#pragma HLS INLINE
    float result = tail_ftz(a)*tail_ftz(b);
#pragma HLS BIND_OP variable=result op=fmul impl=fabric latency=4
    return tail_ftz(result);
}
static float tail_add(float a, float b) {
#pragma HLS INLINE
    float result = tail_ftz(a)+tail_ftz(b);
#pragma HLS BIND_OP variable=result op=fadd impl=fabric latency=5
    return tail_ftz(result);
}
static float tail_sub(float a, float b) {
#pragma HLS INLINE
    float result = tail_ftz(a)-tail_ftz(b);
#pragma HLS BIND_OP variable=result op=fsub impl=fabric latency=5
    return tail_ftz(result);
}

// Only positive normal denominator >=1 occurs in this network's SiLU.
// ARMv7 VRECPE under standard FPSCR returns zero for exponent >=253 (>=2^126).
// Its 256 normal mantissa buckets are the exact architectural estimate,
// NOT a SiLU fit. Integer formula generating the bytes is recorded in prepare.
static float tail_reciprocal_estimate(float denominator) {
#pragma HLS INLINE
    uint32_t u = tail_bits(denominator);
    unsigned exponent = (u >> 23)&255;
    if (exponent >= 253) return 0.f;
    unsigned mantissa = RECIP_ESTIMATE[(u >> 15)&255];
    return tail_float(((253-exponent) << 23) | (mantissa << 15));
}

static float tail_exp_negative(float input) {
#pragma HLS INLINE
    float x = -input;
    const float hi = tail_float(0x42b0c0a5u);
    if (x > hi) x = hi;
    if (x < -hi) x = -hi;
    float fx = tail_add(0.5f, tail_mul(x, tail_float(0x3fb8aa3bu)));
    int exponent = (int)fx; // VC VT truncation, not round-to-nearest.
    float truncated = (float)exponent;
    if (truncated > fx) --exponent;
    float n = (float)exponent;
    // Actual ARM object @0x162: original two constants merged by GCC fast-math.
    float reduced = tail_sub(x, tail_mul(tail_float(0x3f317218u), n));
    float square = tail_mul(reduced, reduced);
    float y = tail_add(tail_float(0x3ab743ceu), tail_mul(tail_float(0x39506967u), reduced));
    y = tail_add(tail_float(0x3c088908u), tail_mul(y, reduced));
    y = tail_add(tail_float(0x3d2aa9c1u), tail_mul(y, reduced));
    y = tail_add(tail_float(0x3e2aaaaau), tail_mul(y, reduced));
    y = tail_add(0.5f, tail_mul(y, reduced));
    y = tail_add(reduced, tail_mul(y, square));
    float power = tail_float(uint32_t(exponent+127) << 23);
    // Object @0x19a: pow2n + y*pow2n, not (1+y)*pow2n.
    return tail_add(power, tail_mul(y, power));
}

static float tail_silu(float input) {
#pragma HLS INLINE
    float denominator = tail_add(tail_exp_negative(input), 1.f);
    float reciprocal = tail_reciprocal_estimate(denominator);
    float step1 = tail_sub(2.f, tail_mul(denominator, reciprocal));
    reciprocal = tail_mul(reciprocal, step1);
    float step2 = tail_sub(2.f, tail_mul(denominator, reciprocal));
    // Object @0x1b2/0x1b6: (input*step2)*reciprocal1.
    return tail_mul(tail_mul(input, step2), reciprocal);
}

static float tail_dequantize(int channel, int32_t sum) {
#pragma HLS INLINE
    float integer = (float)sum;
    return tail_add(tail_float(TAIL_BIAS_BITS[channel]),
                    tail_mul(integer, tail_float(TAIL_SCALE_BITS[channel])));
}
static uint32_t tail_compute(int channel, int32_t sum) {
#pragma HLS INLINE
    return tail_bits(tail_silu(tail_dequantize(channel, sum)));
}
#endif
