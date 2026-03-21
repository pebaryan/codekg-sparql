#include <stdio.h>
#include "utils.h"

typedef struct {
    int x;
    int y;
} Point;

struct Color {
    int r, g, b;
};

int global_count = 0;

int add(int a, int b) {
    return a + b;
}

int main(int argc, char *argv[]) {
    int result = add(1, 2);
    printf("Result: %d\n", result);
    return 0;
}
