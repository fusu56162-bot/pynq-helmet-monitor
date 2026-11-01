#include "../src/chain_float.h"
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include <stdint.h>

template<typename T>
static std::vector<T> read_file(const std::string& path, size_t count) {
    std::ifstream in(path.c_str(), std::ios::binary);
    if (!in) throw std::runtime_error("Missing fixture: "+path);
    std::vector<T> out(count);
    in.read(reinterpret_cast<char*>(out.data()), count*sizeof(T));
    if (in.gcount() != std::streamsize(count*sizeof(T)) || in.peek() != EOF)
        throw std::runtime_error("Bad fixture size: "+path);
    return out;
}
int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error("Need fixture directory and case list");
        const std::string root(argv[1]);
        std::ifstream list((root+"/"+argv[2]).c_str());
        if (!list) throw std::runtime_error("Missing case list");
        std::string name; int w, h, cases = 0;
        while (list >> name >> w >> h) {
            std::vector<uint8_t> bytes = read_file<uint8_t>(root+"/"+name+".rgb.u8", w*h*12);
            size_t count = size_t((w+1)/2)*((h+1)/2)*32;
            std::vector<uint32_t> golden = read_file<uint32_t>(root+"/"+name+".blob4_hwc.u32", count);
            hls::stream<chain_axis32> src, dst;
            for (size_t i = 0; i < bytes.size(); i += 4) {
                chain_axis32 word;
                word.data = unsigned(bytes[i]) | (unsigned(bytes[i+1]) << 8) |
                            (unsigned(bytes[i+2]) << 16) | (unsigned(bytes[i+3]) << 24);
                word.keep = 15; word.strb = 15; word.last = i+4 == bytes.size(); src.write(word);
            }
            unsigned status = 0xffffffff;
            chain_float(src, dst, w, h, status);
            if (status != 0 || !src.empty()) throw std::runtime_error("Input length/status mismatch");
            for (size_t i = 0; i < count; ++i) {
                if (dst.empty()) throw std::runtime_error("Too few output words");
                chain_axis32 out = dst.read();
                if (out.data.to_uint() != golden[i]) {
                    std::cerr << name << " index=" << i << " actual_bits=" << std::hex << out.data.to_uint()
                              << " expected_bits=" << golden[i] << std::dec << std::endl;
                    throw std::runtime_error("Float output not byte exact; tolerance not relaxed");
                }
                if (out.keep != 15 || out.strb != 15 || bool(out.last) != (i+1 == count))
                    throw std::runtime_error("AXIS sideband mismatch");
            }
            if (!dst.empty()) throw std::runtime_error("Too many output words");
            std::cout << "FULL_SEGMENT_FLOAT_BYTE_EXACT_PASS " << name << " values=" << count << std::endl;
            ++cases;
        }
        if (!cases) throw std::runtime_error("No cases executed");
        if (std::string(argv[2]) == "cases.txt") {
            std::ifstream domains((root+"/map_domains.txt").c_str());
            if (!domains) throw std::runtime_error("Missing map domains");
            long verified = 0;
            for (int channel=0;channel<16;++channel) {
                int lo,hi; domains>>lo>>hi;
                if (!domains || hi<lo) throw std::runtime_error("Invalid map domain");
                std::string suffix=channel<10?"0":"";
                suffix+=std::to_string(channel);
                std::vector<int8_t> truth=read_file<int8_t>(root+"/map_"+suffix+".i8",size_t(hi-lo+1));
                for (int x=lo;x<=hi;++x) {
                    unsigned error=0;
                    ap_int<8> value=chain_exact_map(channel,x,error);
                    if (error || value.to_int()!=int(truth[x-lo])) throw std::runtime_error("Exhaustive exact map mismatch");
                    ++verified;
                }
            }
            std::cout<<"EXHAUSTIVE_NEW_ARM_MAPPING_PASS values="<<verified<<std::endl;
            const int sizes[4][2] = {{0, 1}, {1, 0}, {113, 1}, {1, 113}};
            for (int i = 0; i < 4; ++i) {
                hls::stream<chain_axis32> src, dst; unsigned status = 0;
                chain_float(src, dst, sizes[i][0], sizes[i][1], status);
                if (status != 1 || !dst.empty()) throw std::runtime_error("Bad dimensions accepted");
            }
        }
        std::cout << "FLOAT_CHAIN_PASS_NOT_BOARD_OR_WHOLE_MODEL_SPEED_ACCEPTANCE cases=" << cases << std::endl;
        return 0;
    } catch (const std::exception& e) { std::cerr << "FAIL: " << e.what() << std::endl; return 1; }
}
