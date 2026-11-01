#include <ap_axi_sdata.h>
#include <ap_int.h>
#include <hls_stream.h>

typedef ap_axiu<32, 1, 1, 1> axis32_t;

static axis32_t make_pixel(ap_uint<8> c0, ap_uint<8> c1, ap_uint<8> c2,
                           bool last) {
#pragma HLS INLINE
    axis32_t v;
    v.data = (ap_uint<32>(c2) << 16) | (ap_uint<32>(c1) << 8) | c0;
    v.keep = 0xF;
    v.strb = 0xF;
    v.user = 0;
    v.id   = 0;
    v.dest = 0;
    v.last = last ? 1 : 0;
    return v;
}

// Fixed transform:
// 640x480 BGR -> nearest-neighbor 320x240 -> vertical letterbox -> 320x320 RGB.
void vision_preprocess(hls::stream<axis32_t>& src,
                       hls::stream<axis32_t>& dst) {
#pragma HLS INTERFACE axis port=src
#pragma HLS INTERFACE axis port=dst
#pragma HLS INTERFACE s_axilite port=return bundle=control

    const int IN_W = 640;
    const int IN_H = 480;
    const int OUT_W = 320;
    const int PAD_Y = 40;

    // Top padding. RGB gray 114,114,114.
    for (int y = 0; y < PAD_Y; ++y) {
        for (int x = 0; x < OUT_W; ++x) {
#pragma HLS PIPELINE II=1
            dst.write(make_pixel(114, 114, 114, false));
        }
    }

    // Consume every input pixel. Keep one pixel from each 2x2 block.
    for (int y = 0; y < IN_H; ++y) {
        for (int x = 0; x < IN_W; ++x) {
#pragma HLS PIPELINE II=1
            axis32_t in = src.read();
            if (((y & 1) == 0) && ((x & 1) == 0)) {
                ap_uint<8> b = in.data.range(7, 0);
                ap_uint<8> g = in.data.range(15, 8);
                ap_uint<8> r = in.data.range(23, 16);
                // Packed output low-to-high bytes are R, G, B.
                dst.write(make_pixel(r, g, b, false));
            }
        }
    }

    // Bottom padding; TLAST belongs only to the last output pixel.
    for (int y = 0; y < PAD_Y; ++y) {
        for (int x = 0; x < OUT_W; ++x) {
#pragma HLS PIPELINE II=1
            bool last = (y == PAD_Y - 1) && (x == OUT_W - 1);
            dst.write(make_pixel(114, 114, 114, last));
        }
    }
}

