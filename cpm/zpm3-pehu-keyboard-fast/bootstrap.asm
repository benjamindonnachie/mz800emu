; SPDX-License-Identifier: GPL-3.0-or-later
; Native full-RAM boot. No original SUC BIOS or permanent low driver image.
        ORG 0x8000
start:
        DI
        IM 1
        LD SP,0x7F00
        XOR A
        OUT (0xE0),A
        OUT (0xE1),A
        LD HL,0
        LD (HL),A
        LD DE,1
        LD BC,0xFFF
        LDIR
        ; PPI direction, motor/interrupt masks, and explicit SUC80 latch.
        OUT (0xE3),A
        LD A,0x8A
        LD (0xE003),A
        LD A,7
        LD (0xE003),A
        LD A,5
        LD (0xE003),A
        LD A,0x50
        LD (0xE00E),A
        OUT (0xE1),A
        LD DE,32768
        LD HL,0x7000
        LD A,1
        CALL read_blocks
        LD HL,0x7000
        LD DE,magic
        LD B,8
check_magic:
        LD A,(DE)
        CP (HL)
        JP NZ,failed
        INC HL
        INC DE
        DJNZ check_magic
        LD DE,LOADER_LBA
        LD HL,0x100
        LD A,LOADER_SECTORS
        CALL read_blocks
        LD HL,0x100
        LD BC,LOADER_SECTORS*512
        LD DE,LOADER_SUM
        CALL checksum
        CALL LOADER_DRIVER
        LD A,2
        LD (4),A
        LD A,3
        LD (0x7FF0),A
        JP 0x100

; DE=LBA16, HL=destination, A=sector count. Fixed boot area below 65536.
read_blocks:
        LD (remaining),A
next_block:
        PUSH DE
        PUSH HL
        LD A,0xE0
        OUT (0xAE),A
        LD C,0x40
        CALL wait_status
        LD A,1
        OUT (0xAA),A
        LD A,E
        OUT (0xAB),A
        LD A,D
        OUT (0xAC),A
        XOR A
        OUT (0xAD),A
        LD A,0x20
        OUT (0xAF),A
        LD C,8
        CALL wait_status
        POP HL
        LD C,0xA8
        LD B,0
        INIR
        LD B,0
        INIR
        LD C,0x40
        CALL wait_status
        POP DE
        INC DE
        LD A,(remaining)
        DEC A
        LD (remaining),A
        JR NZ,next_block
        RET
wait_status:
        PUSH DE
        LD DE,0x8000
poll:
        IN A,(0xA6)              ; alternate status preserves GIDE byte phase
        CP 0xFF
        JP Z,failed
        BIT 7,A
        JR NZ,busy
        BIT 0,A
        JP NZ,failed
        BIT 5,A
        JP NZ,failed
        AND C
        CP C
        JR Z,ready
busy:
        DEC DE
        LD A,D
        OR E
        JR NZ,poll
        JP failed
ready:
        POP DE
        RET
; Sum of padded block bytes modulo65536. Fail closed on corrupt boot blocks.
checksum:
        PUSH DE
        LD DE,0
sum_loop:
        LD A,(HL)
        ADD A,E
        LD E,A
        JR NC,no_carry
        INC D
no_carry:
        INC HL
        DEC BC
        LD A,B
        OR C
        JR NZ,sum_loop
        POP HL
        OR A
        SBC HL,DE
        JP NZ,failed
        RET
failed:
        DI
        LD A,0xFF
        LD (0x7FF0),A
        ; Visible failure text retains the Sharp ROM colour attributes.
        OUT (0xE3),A
        LD HL,error_text
        LD DE,0xD000
        LD BC,15
        LDIR
halted:
        HALT
        JR halted
magic: DEFM "GIDEZPM!"
error_text: DB 7,9,4,5,0,2,15,15,20,0,5,18,18,15,18
remaining: DB 0
