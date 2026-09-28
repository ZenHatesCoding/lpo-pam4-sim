#include "../src/rng.hpp"
#include <cstdio>
int main(){ using namespace dsh; RkState s; rk_seed(s,42u);
 for(int i=0;i<12;i++){ printf("0x%08x\n", (unsigned)rk_random(s)); } return 0; }
