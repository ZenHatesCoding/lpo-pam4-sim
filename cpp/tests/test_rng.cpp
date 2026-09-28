// test_rng.cpp — 与 numpy RandomState(42) 参考值逐位比对。
#include "../src/rng.hpp"
#include <cstdio>

int main() {
    using namespace dsh;
    RkState s;
    rk_seed(s, 42u);
    printf("randint(0,4,20):");
    for (int i = 0; i < 20; i++) printf(" %lld", (long long)rk_randint(s, 0, 4));
    printf("\n");

    RkState s8;
    rk_seed(s8, 42u);
    printf("randint(0,8,16):");
    for (int i = 0; i < 16; i++) printf(" %lld", (long long)rk_randint(s8, 0, 8));
    printf("\n");

    RkState s3;
    rk_seed(s3, 42u);
    printf("randint(0,3,16):");
    for (int i = 0; i < 16; i++) printf(" %lld", (long long)rk_randint(s3, 0, 3));
    printf("\n");

    RkState g;
    rk_seed(g, 42u);
    printf("normal(0,1,10):\n");
    for (int i = 0; i < 10; i++) printf("%.17g\n", rk_normal(g, 0.0, 1.0));
    return 0;
}