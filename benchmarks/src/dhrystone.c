#include "bench.h"
#define RUNS 80

typedef enum { Ident_1, Ident_2, Ident_3, Ident_4, Ident_5 } Enumeration;
typedef struct Rec_Type {
    struct Rec_Type *Ptr_Comp;
    Enumeration Discr;
    union {
        struct { Enumeration Enum_Comp; int Int_Comp; char Str_Comp[31]; } var_1;
        struct { Enumeration E_Comp_2; char Str_2_Comp[31]; } var_2;
    } variant;
} Rec_Type, *Rec_Pointer;

static Rec_Type rec_a, rec_b;
static Rec_Pointer Ptr_Glob, Next_Ptr_Glob;
static int Int_Glob, Arr_1_Glob[50], Arr_2_Glob[50][50];
static char Ch_1_Glob, Ch_2_Glob;
static int Bool_Glob;

static Enumeration Func_1(char ch1, char ch2) { return ch1 == ch2 ? Ident_2 : Ident_1; }
static int Func_2(char *s1, char *s2) { return strcmp(s1, s2) > 0; }
static void Proc_7(int a, int b, int *out) { int loc = a + 2; *out = b + loc; }
static void Proc_8(int a1[50], int a2[50][50], int i1, int i2) {
    int loc = i1 + 5;
    a1[loc] = i2;
    a1[loc + 1] = a1[loc];
    a2[loc][loc - 1] += 1;
    a2[loc + 20][loc] = a1[loc];
    Int_Glob = 5;
}
static void Proc_6(Enumeration e, Enumeration *out) {
    *out = e;
    if (e == Ident_1) *out = Ident_4;
}
static void Proc_1(Rec_Pointer p) {
    Rec_Pointer n = p->Ptr_Comp;
    *n = *Ptr_Glob;
    p->variant.var_1.Int_Comp = 5;
    n->variant.var_1.Int_Comp = p->variant.var_1.Int_Comp;
    n->Ptr_Comp = p->Ptr_Comp;
    Proc_6(p->variant.var_1.Enum_Comp, &n->variant.var_1.Enum_Comp);
}
static void Proc_2(int *ip) {
    int loc = *ip + 10;
    do { if (Ch_1_Glob == 'A') loc -= 1; } while (0);
    *ip = loc - Int_Glob;
}
static void Proc_4(void) { int b = Ch_1_Glob == 'A'; Bool_Glob = b | Bool_Glob; Ch_2_Glob = 'B'; }
static void Proc_5(void) { Ch_1_Glob = 'A'; Bool_Glob = 0; }

int main(void) {
    Ptr_Glob = &rec_a;
    Next_Ptr_Glob = &rec_b;
    Ptr_Glob->Ptr_Comp = Next_Ptr_Glob;
    Ptr_Glob->Discr = Ident_1;
    Ptr_Glob->variant.var_1.Enum_Comp = Ident_3;
    Ptr_Glob->variant.var_1.Int_Comp = 40;
    strcpy(Ptr_Glob->variant.var_1.Str_Comp, "DHRYSTONE PROGRAM, STRING");
    strcpy(Next_Ptr_Glob->variant.var_1.Str_Comp, "DHRYSTONE PROGRAM, OTHER");
    Arr_2_Glob[8][7] = 10;

    bench_start();
    int checksum = 0;
    for (int run = 1; run <= RUNS; run++) {
        int i1 = 2, i2 = 3, i3 = 0;
        char s1[31], s2[31];
        Enumeration e = Ident_2;
        Proc_5(); Proc_4();
        strcpy(s1, "DHRYSTONE PROGRAM, 1ST");
        strcpy(s2, "DHRYSTONE PROGRAM, 2ND");
        Bool_Glob = !Func_2(s1, s2);
        while (i1 < i2) { i3 = 5 * i1 - i2; Proc_7(i1, i2, &i3); i1++; }
        Proc_8(Arr_1_Glob, Arr_2_Glob, i1, i3);
        Proc_1(Ptr_Glob);
        for (char ch = 'A'; ch <= Ch_2_Glob; ch++) if (e == Func_1(ch, 'C')) Proc_6(Ident_1, &e);
        i2 = i2 * i1;
        i1 = i2 / i3;
        i2 = 7 * (i2 - i3) - i1;
        Proc_2(&i1);
        checksum += i1 + i2 + i3 + Int_Glob + Ptr_Glob->variant.var_1.Int_Comp + run;
    }
    bench_stop();
    uint32_t sig = (uint32_t)checksum ^ (uint32_t)Arr_2_Glob[8][7] ^ (uint32_t)Bool_Glob;
    bench_signature(sig);
    return sig == 0 ? 1 : 0;
}
