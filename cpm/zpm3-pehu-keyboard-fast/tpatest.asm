        ORG 0x100
        LD SP,0x1F00
        LD HL,(6)
        LD A,H
        LD (limit_fill+1),A
        LD (limit_check+1),A
        LD HL,0x2000
fill:   LD A,H
        XOR L
        LD (HL),A
        INC HL
        LD A,H
limit_fill: CP 0
        JR NZ,fill
        LD HL,0x2000
check:  LD A,H
        XOR L
        CP (HL)
        JR NZ,failed
        INC HL
        LD A,H
limit_check: CP 0
        JR NZ,check
        LD A,1
        LD (0x8004),A
        LD DE,success
        LD C,9
        CALL 5
        JP 0
failed: LD A,255
        LD (0x8004),A
        HALT
        JR failed
success: DEFM "Full available TPA pattern test passed."
        DB 13,10,36
