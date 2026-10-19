        ORG 0x100
        LD HL,(6)
        LD A,H
        LD (ceiling+2),A
        LD L,0
        LD (0x8000),HL
        LD DE,256
        OR A
        SBC HL,DE
        LD (0x8002),HL
        LD DE,message
        LD C,9
        CALL 5
ceiling: LD HL,0
        CALL hexword
        LD DE,tail
        LD C,9
        CALL 5
        LD HL,(0x8002)
        LD DE,10000
        CALL decimal_digit
        LD DE,1000
        CALL decimal_digit
        LD DE,100
        CALL decimal_digit
        LD DE,10
        CALL decimal_digit
        LD DE,1
        CALL decimal_digit
        LD DE,bytes_tail
        LD C,9
        CALL 5
        JP 0
decimal_digit:
        LD B,47
decimal_loop:
        INC B
        OR A
        SBC HL,DE
        JR NC,decimal_loop
        ADD HL,DE
        LD A,B
        CALL digit
        RET
hexword:
        LD A,H
        CALL hexbyte
        LD A,L
hexbyte:
        PUSH AF
        RRCA
        RRCA
        RRCA
        RRCA
        CALL nibble
        POP AF
nibble: AND 15
        ADD A,48
        CP 58
        JR C,digit
        ADD A,7
digit:  PUSH HL
        PUSH BC
        PUSH DE
        LD E,A
        LD C,2
        CALL 5
        POP DE
        POP BC
        POP HL
        RET
message: DEFM "Program space: 0100h to below "
        DB 36
tail:   DEFM "h. Available: "
        DB 36
bytes_tail: DEFM " bytes."
        DB 13,10,36
