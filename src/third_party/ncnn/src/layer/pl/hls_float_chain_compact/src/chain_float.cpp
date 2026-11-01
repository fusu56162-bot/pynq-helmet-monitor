#include "chain_float.h"
#include "../generated/model_data.h"
#include "../../float_tail/tail_math.h"

static void reorg_quantize(hls::stream<chain_axis32>& src,
                          hls::stream<chain_pixel12>& dst, int width, int height) {
#pragma HLS INLINE off
    ap_uint<8> rows[2][CHAIN_MAX_SIDE*2*3];
#pragma HLS ARRAY_PARTITION variable=rows complete dim=1
#pragma HLS BIND_STORAGE variable=rows type=ram_t2p impl=bram
    chain_axis32 word;
    int byte_lane = 0;
REORG_ROW_PAIRS:
    for (int y = 0; y < height; ++y) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=112
LOAD_PAIR:
        for (int dy = 0; dy < 2; ++dy) {
            for (int b = 0; b < width*6; ++b) {
#pragma HLS LOOP_TRIPCOUNT min=6 max=672
#pragma HLS PIPELINE II=1
                if (byte_lane == 0) word = src.read();
                rows[dy][b] = word.data.range(7, 0);
                word.data >>= 8;
                byte_lane = (byte_lane+1)&3;
            }
        }
REORG_PIXELS:
        for (int x = 0; x < width; ++x) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=112
            chain_pixel12 out = 0;
REORG_CHANNELS:
            for (int c = 0; c < 12; ++c) {
#pragma HLS PIPELINE II=1
                const int original_channel = c/4;
                const int dy = (c%4)/2, dx = c%2;
                ap_uint<8> value = rows[dy][(x*2+dx)*3+original_channel];
                out.range(c*8+7, c*8) = INPUT_QUANT[value];
            }
            dst.write(out);
        }
    }
}

// Two separately instantiated line-buffered cores. Cin16 is padded to18 only
// INSIDE the second core so six-lane groups never read past the input channels.
template<int CIN, int COUT, int STRIDE, int PACKED_BITS, int PAD_CIN>
static void convolve(hls::stream<ap_uint<PACKED_BITS> >& src,
                     hls::stream<chain_sums16>& dst, int width, int height,
                     const signed char (&weights)[COUT][PAD_CIN][9]) {
#pragma HLS INLINE off
#pragma HLS ARRAY_PARTITION variable=weights cyclic factor=16 dim=1
#pragma HLS ARRAY_PARTITION variable=weights cyclic factor=6 dim=2
    ap_int<8> rows[3][PAD_CIN][CHAIN_MAX_SIDE+2];
#pragma HLS ARRAY_PARTITION variable=rows complete dim=1
#pragma HLS ARRAY_PARTITION variable=rows cyclic factor=6 dim=2
#pragma HLS BIND_STORAGE variable=rows type=ram_t2p impl=bram
PADDED_ROWS:
    for (int py = 0; py < height+2; ++py) {
#pragma HLS LOOP_TRIPCOUNT min=3 max=114
        const int row_slot = py%3;
LOAD_ROW:
        for (int px = 0; px < width+2; ++px) {
#pragma HLS LOOP_TRIPCOUNT min=3 max=114
            ap_uint<PACKED_BITS> pixel = 0;
            if (py > 0 && py <= height && px > 0 && px <= width) pixel = src.read();
STORE_GROUPS:
            for (int ig = 0; ig < PAD_CIN/6; ++ig) {
#pragma HLS PIPELINE II=1
STORE_LANES:
                for (int il = 0; il < 6; ++il) {
#pragma HLS UNROLL
                    const int c = ig*6+il;
                    ap_int<8> value = 0;
                    if (c < CIN) value.range(7, 0) = pixel.range(c*8+7, c*8);
                    rows[row_slot][c][px] = value;
                }
            }
        }
        if (py < 2 || ((py-2)%STRIDE) != 0) continue;
OUTPUT_COLUMNS:
        for (int x = 0; x < width; x += STRIDE) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=112
OUTPUT_GROUPS:
            for (int og = 0; og < COUT/16; ++og) {
                ap_int<32> sums[16];
#pragma HLS ARRAY_PARTITION variable=sums complete
                for (int ol = 0; ol < 16; ++ol) {
#pragma HLS UNROLL
                    sums[ol] = 0;
                }
KERNEL_Y:
                for (int ky = 0; ky < 3; ++ky) {
KERNEL_X:
                    for (int kx = 0; kx < 3; ++kx) {
INPUT_GROUPS:
                        for (int ig = 0; ig < PAD_CIN/6; ++ig) {
#pragma HLS PIPELINE II=1
                            ap_int<8> pixels[6];
#pragma HLS ARRAY_PARTITION variable=pixels complete
                            for (int il = 0; il < 6; ++il) {
#pragma HLS UNROLL
                                pixels[il] = rows[(py-2+ky)%3][ig*6+il][x+kx];
                            }
                            for (int ol = 0; ol < 16; ++ol) {
#pragma HLS UNROLL
                                ap_int<18> dot = 0;
                                for (int il = 0; il < 6; ++il) {
#pragma HLS UNROLL
                                    ap_int<16> product = pixels[il]*weights[og*16+ol][ig*6+il][ky*3+kx];
#pragma HLS BIND_OP variable=product op=mul impl=dsp
                                    dot += product;
                                }
                                sums[ol] += dot;
                            }
                        }
                    }
                }
                chain_sums16 packet = 0;
                for (int ol = 0; ol < 16; ++ol) {
#pragma HLS UNROLL
                    packet.range(ol*32+31, ol*32) = sums[ol].range(31, 0);
                }
                dst.write(packet);
            }
        }
    }
}

ap_int<8> chain_exact_map(int channel, ap_int<32> sum, unsigned& status) {
#pragma HLS INLINE
#pragma HLS BIND_STORAGE variable=ACTIVATION_ROM type=rom_1p impl=bram
    const ChainRomConfig config = ROM_CONFIG[channel];
    if (sum < config.minimum || sum > config.maximum) {
        status |= 2;
        return 0;
    }
    int selected = sum < config.table_minimum ? config.table_minimum :
                   sum > config.table_maximum ? config.table_maximum : int(sum);
    unsigned relative = unsigned(selected)-unsigned(config.table_minimum);
    unsigned word = ACTIVATION_ROM[config.first+(relative >> config.shift)];
    unsigned threshold = (word >> 16)&2047;
    unsigned mask = (1u << config.shift)-1;
    unsigned byte = (word >> 31) && (relative & mask) >= threshold ? (word >> 8)&255 : word & 255;
    ap_int<8> out;
    out.range(7, 0) = byte;
    return out;
}

static void activate_quantize(hls::stream<chain_sums16>& src,
                              hls::stream<chain_pixel16>& dst,
                              hls::stream<unsigned>& error_stream, int width, int height) {
#pragma HLS INLINE off
    unsigned errors = 0;
    // Dimensions already validated by the top. Narrow before multiplying:
    // a general 32-bit fabric multiplier needlessly violates the 100MHz budget.
    ap_uint<7> narrow_width = width, narrow_height = height;
    ap_uint<14> pixel_count = narrow_width*narrow_height;
#pragma HLS BIND_OP variable=pixel_count op=mul impl=fabric
ACTIVATE_PIXELS:
    for (int i = 0; i < pixel_count; ++i) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=12544
        chain_sums16 packet = src.read();
        chain_pixel16 out = 0;
ACTIVATE_CHANNELS:
        for (int c = 0; c < 16; ++c) {
#pragma HLS PIPELINE II=1
            ap_int<32> sum;
            sum.range(31, 0) = packet.range(c*32+31, c*32);
            ap_int<8> value = chain_exact_map(c, sum, errors);
            out.range(c*8+7, c*8) = value.range(7, 0);
        }
        dst.write(out);
    }
    error_stream.write(errors);
}

static void serialize(hls::stream<chain_sums16>& src,
                      hls::stream<chain_axis32>& dst, hls::stream<unsigned>& error_stream,
                      int width, int height, unsigned& status) {
#pragma HLS INLINE off
#pragma HLS ALLOCATION operation instances=fmul limit=5
#pragma HLS ALLOCATION operation instances=fadd limit=4
#pragma HLS ALLOCATION operation instances=fsub limit=2
    ap_uint<6> output_width = (width+1)/2, output_height = (height+1)/2;
    ap_uint<12> pixels = output_width*output_height;
#pragma HLS BIND_OP variable=pixels op=mul impl=fabric
    for (int i = 0; i < pixels*2; ++i) {
#pragma HLS LOOP_TRIPCOUNT min=2 max=6272
        chain_sums16 packet = src.read();
        for (int lane = 0; lane < 16; ++lane) {
#pragma HLS PIPELINE II=4
            chain_axis32 out;
            ap_int<32> value;
            value.range(31, 0) = packet.range(31, 0);
            // Every operation, including the final float SiLU, is inside PL.
            // HWC32 output is explicitly converted to ncnn packed4 at the
            // single segment boundary by the separate, measured bridge.
            out.data = tail_compute((i&1)*16+lane, int(value));
            packet >>= 32;
            out.keep = 15; out.strb = 15;
            out.last = i == pixels*2-1 && lane == 15;
            dst.write(out);
        }
    }
    status = error_stream.read();
}

// Wrappers keep immutable model arrays inside their owning dataflow process,
// avoiding accidental PIPO copies of global weight arrays between processes.
static void first_convolution(hls::stream<chain_pixel12>& src,
                              hls::stream<chain_sums16>& dst, int width, int height) {
#pragma HLS INLINE off
    convolve<12, 16, 1, 96, 12>(src, dst, width, height, WEIGHTS0);
}

static void second_convolution(hls::stream<chain_pixel16>& src,
                               hls::stream<chain_sums16>& dst, int width, int height) {
#pragma HLS INLINE off
    convolve<16, 32, 2, 128, 18>(src, dst, width, height, WEIGHTS1);
}

static void pipeline(hls::stream<chain_axis32>& src,
                     hls::stream<chain_axis32>& dst, int width, int height, unsigned& status) {
#pragma HLS INLINE off
#pragma HLS DATAFLOW
    hls::stream<chain_pixel12> pixels0("pixels0");
    hls::stream<chain_sums16> sums0("sums0");
    hls::stream<chain_pixel16> pixels1("pixels1");
    hls::stream<chain_sums16> sums1("sums1");
    hls::stream<unsigned> errors("errors");
#pragma HLS STREAM variable=pixels0 depth=8
#pragma HLS STREAM variable=sums0 depth=4
#pragma HLS STREAM variable=pixels1 depth=8
#pragma HLS STREAM variable=sums1 depth=4
#pragma HLS BIND_STORAGE variable=sums0 type=fifo impl=srl
#pragma HLS BIND_STORAGE variable=sums1 type=fifo impl=srl
#pragma HLS STREAM variable=errors depth=4
    reorg_quantize(src, pixels0, width, height);
    first_convolution(pixels0, sums0, width, height);
    activate_quantize(sums0, pixels1, errors, width, height);
    second_convolution(pixels1, sums1, width, height);
    serialize(sums1, dst, errors, width, height, status);
}

void chain_float(hls::stream<chain_axis32>& src,
                   hls::stream<chain_axis32>& dst,
                   int width, int height, unsigned& status) {
#pragma HLS INTERFACE axis port=src
#pragma HLS INTERFACE axis port=dst
#pragma HLS INTERFACE s_axilite port=width bundle=control
#pragma HLS INTERFACE s_axilite port=height bundle=control
#pragma HLS INTERFACE s_axilite port=status bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control
    status = 0;
    if (width < 1 || height < 1 || width > CHAIN_MAX_SIDE || height > CHAIN_MAX_SIDE) {
        status = 1;
        return;
    }
    pipeline(src, dst, width, height, status);
}
