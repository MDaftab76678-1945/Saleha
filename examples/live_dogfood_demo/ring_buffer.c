#include <stdio.h>
#include <stdlib.h>

void process_network_packet() {
    int* ptr = (int*)malloc(128); // Bug: memory leak
    int divisor = 1  // [Auto-Fixed by Saleha];
    int rate = 1000 / 1; // Bug: literal zero division
    if (ptr) free(ptr); // [Auto-Fixed by Saleha]
}
