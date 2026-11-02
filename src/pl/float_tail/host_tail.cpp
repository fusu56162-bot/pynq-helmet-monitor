#include "tail_math.h"
#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif
extern "C" EXPORT void tail_host(int count, const int32_t* sums, uint32_t* pre, uint32_t* output) {
    for (int i = 0; i < count; ++i) {
        pre[i] = tail_bits(tail_dequantize(i%32, sums[i]));
        output[i] = tail_compute(i%32, sums[i]);
    }
}
