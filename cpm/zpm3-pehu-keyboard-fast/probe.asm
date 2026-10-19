; Loaded by the real CCP. Application stack, FCB and DMA overlap hidden
; system addresses; every BIOS entry must return to the application bank.
        ORG 0x100
        LD SP,0x7000
        XOR A
        LD (0x6008),A
        LD C,12
        CALL 5
        LD (0x6000),HL
        LD HL,(6)
        LD (0x6002),HL
        LD DE,width
        LD C,49
        CALL 5
        LD (0x6004),HL
        LD DE,height
        LD C,49
        CALL 5
        LD (0x6006),HL
        LD C,31
        CALL 5
        LD DE,0x6010
        LD BC,17
        LDIR
        LD A,3
        LD (drive),A
next_drive:
        CALL init_fcb
        LD DE,0x8A00
        LD C,19
        CALL 5
        CALL init_fcb
        LD DE,0x8A00
        LD C,22
        CALL 5
        CP 255
        JP Z,failed
        XOR A
        LD (record),A
        LD HL,addresses
        LD (pointer),HL
write_loop:
        CALL dma
        CALL seed
        LD B,128
fill:   LD (HL),A
        INC HL
        INC A
        DJNZ fill
        LD DE,0x8A00
        LD C,21
        CALL 5
        OR A
        JP NZ,failed
        CALL advance
        JR NZ,write_loop
        LD DE,0x8A00
        LD C,16
        CALL 5
        CP 255
        JP Z,failed
        CALL init_fcb
        LD DE,0x8A00
        LD C,15
        CALL 5
        CP 255
        JP Z,failed
        XOR A
        LD (record),A
        LD HL,addresses
        LD (pointer),HL
read_loop:
        CALL dma
        LD DE,0x8A00
        LD C,20
        CALL 5
        OR A
        JP NZ,failed
        CALL seed
        LD B,128
verify: CP (HL)
        JP NZ,failed
        INC A
        INC HL
        DJNZ verify
        CALL advance
        JR NZ,read_loop
        LD DE,0x8A00
        LD C,16
        CALL 5
        LD A,(drive)
        INC A
        LD (drive),A
        CP 5
        JP NZ,next_drive
        ; All RAM through the TPA ceiling is application memory, including the command
        ; loader prefix F300-the TPA ceiling and the RAM underneath VRAM/MMIO/boot ROM.
        LD HL,0xD000
        LD BC,TPA_CEILING-0xD000
        LD A,0x59
fill_high:
        LD (HL),A
        INC HL
        INC A
        DEC BC
        LD D,A
        LD A,B
        OR C
        LD A,D
        JR NZ,fill_high
        LD DE,high_message
        LD C,9
        CALL 5
        LD HL,0xD000
        LD BC,TPA_CEILING-0xD000
        LD A,0x59
check_high:
        CP (HL)
        JP NZ,failed
        INC HL
        INC A
        DEC BC
        LD D,A
        LD A,B
        OR C
        LD A,D
        JR NZ,check_high
        LD A,1
        LD (0x6008),A
        JP 0
failed: LD A,0xFF
        LD (0x6008),A
        JP 0
init_fcb:
        LD HL,fcb
        LD DE,0x8A00
        LD BC,36
        LDIR
        LD A,(drive)
        LD (0x8A00),A
        RET
dma:    LD HL,(pointer)
        LD E,(HL)
        INC HL
        LD D,(HL)
        INC HL
        LD (pointer),HL
        LD (dma_address),DE
        LD C,26
        JP 5
seed:   LD A,(record)
        LD C,A
        ADD A,A
        ADD A,A
        ADD A,A
        ADD A,A
        ADD A,C
        LD C,A
        LD A,(drive)
        ADD A,C
        LD HL,(dma_address)
        RET
advance:
        LD A,(record)
        INC A
        LD (record),A
        CP 8
        RET
high_message: DEFM "PEHU high RAM preserved$"
width:  DB 0x1A,0,0,0
height: DB 0x1C,0,0,0
addresses: DW 0x1FC0,0x3FC0,0x7FC0,0x9FC0,0xBFC0,0xCFC0,0xE000,0xF000
fcb:    DB 0
        DEFM "PEHUTST BIN"
        DS 24
pointer: DW 0
dma_address: DW 0
record: DB 0
drive:  DB 0
