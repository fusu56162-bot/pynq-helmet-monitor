// Local experimental C ABI. ncnn itself is distributed under its bundled license.
// No resizing, BGR/RGB conversion, normalization, sigmoid or NMS here.
#include "net.h"
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <exception>
#include <memory>
#include <stdexcept>

#if !defined(__arm__) || !defined(__ARM_NEON)
#error "Build this bridge for ARMv7 with NEON"
#endif

namespace {
struct Handle { ncnn::Net net; };
int fail(char* err, int cap, const char* message) {
    if (err && cap > 0) std::snprintf(err, static_cast<size_t>(cap), "%s", message);
    return -1;
}
}

extern "C" {
const char* rider_build_info() {
    return "ncnn=" NCNN_VERSION_STRING ";armv7-neon;fp32;vulkan=off;abi=1";
}
void* rider_create(const char* param, const char* bin, int threads, char* err, int cap) {
    try {
        if (!param || !bin || (threads != 1 && threads != 2))
            throw std::runtime_error("Expected model paths and threads=1 or 2");
        std::unique_ptr<Handle> h(new Handle);
        h->net.opt.num_threads = threads;
        h->net.opt.use_vulkan_compute = false;
        h->net.opt.use_fp16_packed = false;
        h->net.opt.use_fp16_storage = false;
        h->net.opt.use_fp16_arithmetic = false;
        h->net.opt.use_bf16_storage = false;
        h->net.opt.use_int8_inference = false;
        if (h->net.load_param(param) != 0) throw std::runtime_error("load_param failed");
        if (h->net.load_model(bin) != 0) throw std::runtime_error("load_model failed");
        return h.release();
    } catch (const std::exception& e) { fail(err, cap, e.what()); }
      catch (...) { fail(err, cap, "Unknown model-load error"); }
    return nullptr;
}
int rider_forward(void* ptr, const float* src, size_t input_count,
                  float* dst, size_t output_count, char* err, int cap) {
    try {
        if (!ptr || !src || !dst || input_count != 3u*320u*320u || output_count != 6300u*9u)
            throw std::runtime_error("Invalid handle, buffers or element counts");
        Handle& h = *static_cast<Handle*>(ptr);
        ncnn::Mat input(320, 320, 3);
        if (input.empty()) throw std::runtime_error("Input allocation failed");
        for (int c = 0; c < 3; ++c) {
            float* channel = input.channel(c);
            std::memcpy(channel, src + c*320*320, 320u*320u*sizeof(float));
        }
        ncnn::Extractor ex = h.net.create_extractor();
        ex.set_light_mode(true);
        if (ex.input("in0", input) != 0) throw std::runtime_error("in0 input failed");
        ncnn::Mat out;
        if (ex.extract("out0", out, 0) != 0) throw std::runtime_error("out0 extraction failed");
        if (out.dims != 2 || out.w != 9 || out.h != 6300 || out.elempack != 1 || out.elembits() != 32)
            throw std::runtime_error("Output must be unpacked FP32 [6300,9]");
        for (int r = 0; r < 6300; ++r)
            std::memcpy(dst + r*9, out.row(r), 9u*sizeof(float));
        return 0;
    } catch (const std::exception& e) { return fail(err, cap, e.what()); }
      catch (...) { return fail(err, cap, "Unknown inference error"); }
}
void rider_destroy(void* ptr) { delete static_cast<Handle*>(ptr); }
}
