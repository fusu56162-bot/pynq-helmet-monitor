// Experimental cut-point adapter only. All remaining ncnn operators are linked
// from the unchanged, SHA-pinned ARM archive. No replacement activation math.
#include "net.h"
#include "cpu.h"
#include "layer/arm/convolution_arm.h"
#include <cstdio>
#include <cstring>
#include <exception>
#include <memory>
#include <stdexcept>
#include <stdint.h>
#if !defined(__arm__) || !defined(__ARM_NEON)
#error "The whole-model experiment requires ARMv7 NEON"
#endif
#if !NCNN_INT8
#error "The existing archive must support INT8"
#endif
extern "C" int chain_boundary_hwc_to_packed4(const uint32_t*,size_t,uint32_t*,size_t,int,int);
namespace {
struct Handle { ncnn::Net net; };
struct FPState {
    int old;
    explicit FPState(int mode):old(ncnn::get_flush_denormals()) { ncnn::set_flush_denormals(mode); }
    ~FPState() { ncnn::set_flush_denormals(old); }
};
void require(bool value,const char* text) { if(!value) throw std::runtime_error(text); }
int fail(char* err,int cap,const char* text) {
    if(err && cap>0) std::snprintf(err,static_cast<size_t>(cap),"%s",text);
    return -1;
}
ncnn::Mat input_mat(const float* src) {
    require(src!=nullptr,"Null input");
    ncnn::Mat m(224,224,3);
    require(!m.empty(),"Input allocation failed");
    for(int c=0;c<3;++c) std::memcpy(m.channel(c),src+c*224*224,224*224*4);
    return m;
}
ncnn::Mat extract(Handle& h,const ncnn::Mat& input,const char* input_name,const char* output_name) {
    ncnn::Extractor ex=h.net.create_extractor();
    ex.set_light_mode(true);
    require(ex.input(input_name,input)==0,"Input blob failed");
    ncnn::Mat out;
    require(ex.extract(output_name,out,0)==0,"Extraction failed");
    return out;
}
void copy_full(const ncnn::Mat& out,float* dst,size_t count) {
    require(dst && count==3087u*9 && !out.empty() && out.dims==2 && out.w==9 &&
            out.h==3087 && out.elempack==1 && out.elembits()==32,"Full output contract failed");
    for(int r=0;r<3087;++r) std::memcpy(dst+r*9,out.row(r),9*4);
}
}
extern "C" {
const char* whole_chain_info() { return "whole-chain-v1;ncnn=" NCNN_VERSION_STRING ";224;recover5;owned-packed4"; }
void* whole_create(const char* param,const char* bin,char* err,int cap) {
    try {
        require(param && bin,"Null model paths");
        std::unique_ptr<Handle> h(new Handle);
        h->net.opt.num_threads=2;
        h->net.opt.use_vulkan_compute=false;
        h->net.opt.use_fp16_packed=false;
        h->net.opt.use_fp16_storage=false;
        h->net.opt.use_fp16_arithmetic=false;
        h->net.opt.use_bf16_storage=false;
        h->net.opt.use_int8_inference=true;
        require(h->net.load_param(param)==0 && h->net.load_model(bin)==0,"Model load failed");
        int found=0;
        const std::vector<ncnn::Layer*>& layers=h->net.layers();
        for(size_t i=0;i<layers.size();++i) {
            if(layers[i]->name=="conv_0" || layers[i]->name=="conv_1") {
                require(layers[i]->type=="Convolution","Unexpected prefix layer type");
                const ncnn::Convolution_arm& c=*static_cast<ncnn::Convolution_arm*>(layers[i]);
                const int s=layers[i]->name=="conv_0"?0:1;
                require(c.num_output==(s?32:16) && c.kernel_w==3 && c.kernel_h==3 &&
                        c.stride_w==s+1 && c.stride_h==s+1 && c.dilation_w==1 && c.dilation_h==1 &&
                        c.pad_left==1 && c.pad_right==1 && c.pad_top==1 && c.pad_bottom==1 &&
                        c.int8_scale_term==2 && c.activation_type==0 && c.bias_term==1,
                        "Frozen prefix configuration changed");
                ++found;
            }
            if(layers[i]->name=="silu_75" || layers[i]->name=="silu_76") {
                require(layers[i]->type=="Swish","Original activation changed"); ++found;
            }
        }
        require(found==4,"Frozen prefix layers missing");
        return h.release();
    } catch(const std::exception& e) { fail(err,cap,e.what()); }
      catch(...) { fail(err,cap,"Unknown create error"); }
    return nullptr;
}
void whole_destroy(void* ptr) { delete static_cast<Handle*>(ptr); }
int whole_full(void* ptr,const float* src,size_t count,float* dst,size_t out_count,char* err,int cap) {
    try {
        require(ptr && count==3u*224*224,"Full input contract failed");
        Handle& h=*static_cast<Handle*>(ptr); FPState fp(h.net.opt.flush_denormals);
        copy_full(extract(h,input_mat(src),"in0","out0"),dst,out_count);
        return 0;
    } catch(const std::exception& e) { return fail(err,cap,e.what()); }
      catch(...) { return fail(err,cap,"Unknown full error"); }
}
int whole_boundary(void* ptr,const float* src,size_t count,uint32_t* hwc,size_t out_count,char* err,int cap) {
    // CPU preflight reference only, NEVER called on the FPGA timed path.
    try {
        require(ptr && count==3u*224*224 && hwc && out_count==32u*56*56,"Boundary contract failed");
        Handle& h=*static_cast<Handle*>(ptr); FPState fp(h.net.opt.flush_denormals);
        ncnn::Mat packed=extract(h,input_mat(src),"in0","4"), chw;
        ncnn::convert_packing(packed,chw,1,h.net.opt);
        require(!chw.empty() && chw.dims==3 && chw.w==56 && chw.h==56 && chw.c==32 &&
                chw.elempack==1 && chw.elembits()==32,"Boundary shape failed");
        for(int c=0;c<32;++c) {
            const float* src_plane=chw.channel(c);
            for(int p=0;p<56*56;++p) std::memcpy(hwc+p*32+c,src_plane+p,4);
        }
        return 0;
    } catch(const std::exception& e) { return fail(err,cap,e.what()); }
      catch(...) { return fail(err,cap,"Unknown boundary error"); }
}
int whole_resume_hwc(void* ptr,const uint32_t* hwc,size_t count,float* dst,size_t out_count,char* err,int cap) {
    try {
        require(ptr && hwc && count==32u*56*56,"Resume input contract failed");
        Handle& h=*static_cast<Handle*>(ptr); FPState fp(h.net.opt.flush_denormals);
        // Owned ncnn memory. Never alias HWC DMA memory as a packed Mat.
        ncnn::Mat packed(56,56,8,static_cast<size_t>(16),4,nullptr);
        require(!packed.empty() && packed.cstep==56u*56,"Packed allocation/alignment failed");
        require(chain_boundary_hwc_to_packed4(hwc,count,static_cast<uint32_t*>(packed.data),count,56,56)==0,
                "HWC to owned packed4 failed");
        copy_full(extract(h,packed,"4","out0"),dst,out_count);
        return 0;
    } catch(const std::exception& e) { return fail(err,cap,e.what()); }
      catch(...) { return fail(err,cap,"Unknown resume error"); }
}
}
