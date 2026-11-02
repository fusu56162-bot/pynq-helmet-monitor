// Candidate-only dynamic-size adapter; unchanged ncnn operators and weights.
#include "net.h"
#include <cstdio>
#include <cstring>
#include <exception>
#include <memory>
#include <stdexcept>
#if !defined(__arm__) || !defined(__ARM_NEON)
#error "Native ARMv7 NEON required"
#endif
namespace {
struct Handle { ncnn::Net net; int side; int rows; };
int fail(char* err, int cap, const char* message) {
    if (err && cap > 0) std::snprintf(err, static_cast<size_t>(cap), "%s", message);
    return -1;
}
}
extern "C" {
const char* small_build_info() { return "small-v1;ncnn=" NCNN_VERSION_STRING ";armv7-neon;fp32-or-int8;abi=1"; }
void* small_create(const char* param, const char* bin, int side, int int8, char* err, int cap) {
    try {
        if (!param || !bin || (side != 224 && side != 256 && side != 320) || (int8 != 0 && int8 != 1))
            throw std::runtime_error("Invalid paths, side or precision flag");
        std::unique_ptr<Handle> h(new Handle);
        h->side = side;
        h->rows = 3*((side/8)*(side/8)+(side/16)*(side/16)+(side/32)*(side/32));
        h->net.opt.num_threads = 2;
        h->net.opt.use_vulkan_compute = false;
        h->net.opt.use_fp16_packed = false;
        h->net.opt.use_fp16_storage = false;
        h->net.opt.use_fp16_arithmetic = false;
        h->net.opt.use_bf16_storage = false;
        h->net.opt.use_int8_inference = int8 != 0;
        if (h->net.load_param(param) || h->net.load_model(bin)) throw std::runtime_error("Model load failed");
        return h.release();
    } catch (const std::exception& e) { fail(err, cap, e.what()); }
      catch (...) { fail(err, cap, "Unknown model load failure"); }
    return nullptr;
}
int small_forward(void* ptr, const float* src, size_t count, float* dst, size_t out_count, char* err, int cap) {
    try {
        if (!ptr || !src || !dst) throw std::runtime_error("Null buffer/handle");
        Handle& h = *static_cast<Handle*>(ptr);
        size_t plane = static_cast<size_t>(h.side)*h.side;
        if (count != 3*plane || out_count != static_cast<size_t>(h.rows)*9) throw std::runtime_error("Wrong buffer size");
        ncnn::Mat input(h.side, h.side, 3);
        if (input.empty()) throw std::runtime_error("Allocation failed");
        for (int c = 0; c < 3; ++c) std::memcpy(input.channel(c), src+c*plane, plane*sizeof(float));
        ncnn::Extractor ex = h.net.create_extractor();
        ex.set_light_mode(true);
        if (ex.input("in0", input)) throw std::runtime_error("Input failed");
        ncnn::Mat out;
        if (ex.extract("out0", out, 0)) throw std::runtime_error("Output failed");
        if (out.dims != 2 || out.w != 9 || out.h != h.rows || out.elempack != 1 || out.elembits() != 32)
            throw std::runtime_error("Unexpected output shape/type");
        for (int r = 0; r < h.rows; ++r) std::memcpy(dst+r*9, out.row(r), 9*sizeof(float));
        return 0;
    } catch (const std::exception& e) { return fail(err, cap, e.what()); }
      catch (...) { return fail(err, cap, "Unknown forward failure"); }
}
void small_destroy(void* ptr) { delete static_cast<Handle*>(ptr); }
}
