float f;

// Impl of ABS
int abs2(int y);

int abs2(int y) {
    if(y < 0) { return -y; }
    else { return y; }
}

// This is a test
struct Test {
    int test;
    float floaty_mcfloatface;
};

struct Test2{

};

struct M {
    int test;
};

void main() {
    string cast;
    struct Test a_struct;
    for(int i = 0; i < 10; ++i) {
        abs2(i);
    }
}
