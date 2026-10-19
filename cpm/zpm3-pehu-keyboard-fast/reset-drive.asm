; ZCCP February1993 calls BDOS13, which selects A:. Preserve the current
; drive across that reset so C:/D: boot and warm starts remain usable.
        ORG 0x1200
        LD C,25
        CALL 0x12C
        PUSH AF
        LD A,13
        LD (0xD7E),A
        LD C,A
        CALL 0x12C
        POP DE
        PUSH HL
        PUSH AF
        LD E,D
        LD D,0
        LD C,14
        CALL 0x12C
        POP AF
        POP HL
        RET
