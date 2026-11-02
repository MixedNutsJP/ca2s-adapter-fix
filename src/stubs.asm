; Export trampolines. Each export loads its index and enters proxy_dispatch,
; which asks proxy_resolve for the target and tail-jumps to it with every
; argument register intact, so these work without knowing any signature.

EXTERN proxy_resolve:PROC

.code

proxy_dispatch PROC FRAME
    sub     rsp, 88h
    .allocstack 88h
    .endprolog

    mov     [rsp+20h], rcx
    mov     [rsp+28h], rdx
    mov     [rsp+30h], r8
    mov     [rsp+38h], r9
    movaps  [rsp+40h], xmm0
    movaps  [rsp+50h], xmm1
    movaps  [rsp+60h], xmm2
    movaps  [rsp+70h], xmm3

    mov     ecx, eax
    call    proxy_resolve

    mov     rcx, [rsp+20h]
    mov     rdx, [rsp+28h]
    mov     r8,  [rsp+30h]
    mov     r9,  [rsp+38h]
    movaps  xmm0, [rsp+40h]
    movaps  xmm1, [rsp+50h]
    movaps  xmm2, [rsp+60h]
    movaps  xmm3, [rsp+70h]

    add     rsp, 88h
    jmp     rax
proxy_dispatch ENDP

STUB MACRO index
proxy_stub_&index& PROC
    mov     eax, index
    jmp     proxy_dispatch
proxy_stub_&index& ENDP
ENDM

STUB 0
STUB 1
STUB 2
STUB 3
STUB 4
STUB 5
STUB 6
STUB 7
STUB 8
STUB 9
STUB 10
STUB 11
STUB 12
STUB 13
STUB 14
STUB 15
STUB 16
STUB 17
STUB 18
STUB 19

END
