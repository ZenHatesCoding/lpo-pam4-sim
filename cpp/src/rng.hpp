// rng.hpp — numpy RandomState (legacy MT19937) 逐位兼容的随机数发生器。
//
// 复现 numpy/random/mtrand/randomkit.c 的口径：RandomState(seed) 用 init_genrand
// 直插种子（1812433253 递推），randint(0,k) 用 rk_interval（掩码拒绝采样），
// normal(loc,scale) 用 rk_gauss（Marsaglia 极坐标法 + has_gauss 缓存）。
// 与 np.random.RandomState(seed).randint / .normal 输出逐位一致，用于保证
// C++ 平台与 Python 平台在同一 seed 下拿到完全相同随机输入。
#pragma once

#include <cstdint>
#include <cmath>

namespace dsh {

static constexpr int RK_STATE_LEN = 624;
static constexpr int RK_STATE_M = 397;
static constexpr uint32_t RK_MATRIX_A = 0x9908b0dfu;
static constexpr uint32_t UPPER_MASK = 0x80000000u;
static constexpr uint32_t LOWER_MASK = 0x7fffffffu;

struct RkState {
    uint32_t key[RK_STATE_LEN];
    int pos = 0;
    int has_gauss = 0;
    double gauss = 0.0;
};

// init_genrand（numpy rk_seed）：1812433253 递推。
inline void rk_seed(RkState& s, uint32_t seed) {
    seed &= 0xffffffffu;
    for (int p = 0; p < RK_STATE_LEN; p++) {
        s.key[p] = seed;
        seed = (1812433253u * (seed ^ (seed >> 30)) + (uint32_t)(p + 1)) & 0xffffffffu;
    }
    s.pos = RK_STATE_LEN;
    s.has_gauss = 0;
    s.gauss = 0.0;
}

// mt19937 genrand_int32（numpy rk_mt19937_next）。
inline uint32_t rk_random(RkState& s) {
    uint32_t y;
    if (s.pos >= RK_STATE_LEN) {
        int i;
        for (i = 0; i < RK_STATE_LEN - RK_STATE_M; i++) {
            y = (s.key[i] & UPPER_MASK) | (s.key[i + 1] & LOWER_MASK);
            s.key[i] = s.key[i + RK_STATE_M] ^ (y >> 1) ^ ((0u - (y & 1u)) & RK_MATRIX_A);
        }
        for (; i < RK_STATE_LEN - 1; i++) {
            y = (s.key[i] & UPPER_MASK) | (s.key[i + 1] & LOWER_MASK);
            s.key[i] = s.key[i + RK_STATE_M - RK_STATE_LEN] ^ (y >> 1) ^ ((0u - (y & 1u)) & RK_MATRIX_A);
        }
        y = (s.key[RK_STATE_LEN - 1] & UPPER_MASK) | (s.key[0] & LOWER_MASK);
        s.key[RK_STATE_LEN - 1] = s.key[RK_STATE_M - 1] ^ (y >> 1) ^ ((0u - (y & 1u)) & RK_MATRIX_A);
        s.pos = 0;
    }
    y = s.key[s.pos++];
    y ^= (y >> 11);
    y ^= (y << 7) & 0x9d2c5680u;
    y ^= (y << 15) & 0xefc60000u;
    y ^= (y >> 18);
    return y;
}

// numpy rk_double：a*2^26 + b 的 53 位小数。
inline double rk_double(RkState& s) {
    uint64_t a = (uint64_t)(rk_random(s) >> 5);
    uint64_t b = (uint64_t)(rk_random(s) >> 6);
    return (double)(a * 67108864ULL + b) / 9007199254740992.0;
}

// numpy rk_interval(max)：掩码拒绝采样，返回 [0, max)。
inline uint32_t rk_interval(uint32_t max, RkState& s) {
    if (max == 0) return 0;
    uint32_t mask = max;
    mask |= mask >> 1;
    mask |= mask >> 2;
    mask |= mask >> 4;
    mask |= mask >> 8;
    mask |= mask >> 16;
    uint32_t value;
    do {
        value = rk_random(s) & mask;
    } while (value >= max);
    return value;
}

// numpy rk_gauss：Marsaglia 极坐标法（has_gauss 缓存）。
inline double rk_gauss(RkState& s) {
    if (s.has_gauss) {
        double tmp = s.gauss;
        s.gauss = 0.0;
        s.has_gauss = 0;
        return tmp;
    }
    double f, x1, x2, r2;
    do {
        x1 = 2.0 * rk_double(s) - 1.0;
        x2 = 2.0 * rk_double(s) - 1.0;
        r2 = x1 * x1 + x2 * x2;
    } while (r2 >= 1.0 || r2 == 0.0);
    f = std::sqrt(-2.0 * std::log(r2) / r2);
    s.gauss = f * x1;
    s.has_gauss = 1;
    return f * x2;
}

// numpy rk_normal：loc + scale * rk_gauss。
inline double rk_normal(RkState& s, double loc, double scale) {
    return loc + scale * rk_gauss(s);
}

// numpy legacy RandomState.randint(low, high) 的逐位口径：
//   range = high - low 为 2 的幂时 -> 直接 rk_random & (range-1)（无拒绝采样）；
//   range <= 2^31 且非幂次   -> rk_interval(range)（掩码拒绝采样）。
// 范围 4/8/2^31 均实测与 np.random.RandomState(seed).randint(low, high) 逐位一致。
inline int64_t rk_randint(RkState& s, int64_t low, int64_t high) {
    uint64_t range = (uint64_t)(high - low);
    if (range == 0) return low;
    if ((range & (range - 1)) == 0) {
        return low + (int64_t)(rk_random(s) & (uint32_t)(range - 1));
    }
    return low + (int64_t)rk_interval((uint32_t)range, s);
}

} // namespace dsh