#ifndef RIDER_CHAIN_FLOAT_H
#define RIDER_CHAIN_FLOAT_H
#include <ap_axi_sdata.h>
#include <ap_int.h>
#include <hls_stream.h>

typedef ap_axiu<32, 0, 0, 0> chain_axis32;
typedef ap_uint<96> chain_pixel12;
typedef ap_uint<128> chain_pixel16;
typedef ap_uint<512> chain_sums16;
static const int CHAIN_MAX_SIDE = 112;

// DEVELOPMENT CANDIDATE, NOT BOARD/ACCURACY/PERFORMANCE ACCEPTANCE.
// Model-specialized, immutable verified recover5 weights and ARM-generated ROM.
// Input: RGB byte raster, 2*width by 2*height; 4 bytes/word, low byte first.
// RGB channels mean the same three planes as the frozen input, no BGR swap.
// Output: complete segment float32 in HWC32, one IEEE32/word, final TLAST.
// Internally: byte lookup + Reorg -> Conv0 -> exact original activation/quant
// map -> Conv1 stride2 -> original-binary-order dequantize/bias/float SiLU.
// No middle-layer traffic to ARM or DDR. This stream is NOT ncnn packed4;
// the explicit segment-boundary bridge must transpose, without recomputing
// activation, and its copy cost MUST be included in whole-model timing.
// Byte input changes model API; all input packing costs must also be included.
void chain_float(hls::stream<chain_axis32>& src,
                   hls::stream<chain_axis32>& dst,
                   int width, int height, unsigned& status);

// Same synthesis decoder, exposed to the C test bench for exhaustive truth-map
// verification. Outside the conservative domain sets status bit 1, never clamps
// silently to the domain. Constant-tail trimming inside it is lossless.
ap_int<8> chain_exact_map(int channel, ap_int<32> sum, unsigned& status);
#endif
