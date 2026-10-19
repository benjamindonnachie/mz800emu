; Exercise BDOS deblocking, shared C/D buffers and untouched sector quarters.
        ORG 0x100
        LD SP,0x7000
        LD A,1
        LD (0x8005),A
        LD DE,c_fcb
        LD C,15
        CALL checked_fcb
        LD A,2
        LD (0x8005),A
        LD DE,d_fcb
        LD C,15
        CALL checked_fcb
        LD A,3
        LD (0x8005),A
        ; Four-record I/O into an unaligned 512-byte application DMA.
        LD DE,4
        LD C,44
        CALL 5
        LD DE,0x40FF
        LD C,26
        CALL 5
        LD DE,c_fcb
        LD C,20
        CALL 5
        OR A
        JP NZ,failed
        LD HL,0x40FF
        LD BC,512
multi_check:
        LD A,(HL)
        CP 0x5A
        JP NZ,failed
        INC HL
        DEC BC
        LD A,B
        OR C
        JR NZ,multi_check
        LD DE,1
        LD C,44
        CALL 5
        LD HL,records
        LD (next),HL
next_pair:
        LD A,4
        LD (0x8005),A
        LD HL,(next)
        LD E,(HL)
        INC HL
        LD D,(HL)
        INC HL
        LD (next),HL
        LD A,D
        AND E
        INC A
        JR Z,all_done
        LD (c_fcb+33),DE
        LD (d_fcb+33),DE
        LD DE,c_fcb
        LD A,0x5A
        LD (old_byte),A
        LD A,0x3C
        LD (new_byte),A
        CALL update
        LD DE,d_fcb
        LD A,0xA5
        LD (old_byte),A
        LD A,0xC3
        LD (new_byte),A
        CALL update
        JR next_pair
all_done:
        LD A,5
        LD (0x8005),A
        LD DE,c_fcb
        LD C,16
        CALL checked_fcb
        LD DE,d_fcb
        LD C,16
        CALL checked_fcb
        LD E,0
        LD C,48
        CALL 5
        OR A
        JP NZ,failed
        LD A,0xA5
        LD (0x8004),A
        JP 0
update:
        LD (current),DE
        LD DE,0x40FF
        LD C,26
        CALL 5
        LD DE,(current)
        LD C,33
        CALL 5
        OR A
        JP NZ,failed
        LD HL,0x40FF
        LD B,128
        LD A,(old_byte)
read_check:
        CP (HL)
        JP NZ,failed
        INC HL
        DJNZ read_check
        LD HL,0x40FF
        LD B,128
        LD A,(new_byte)
fill:   LD (HL),A
        INC HL
        DJNZ fill
        LD DE,(current)
        LD C,34
        CALL 5
        OR A
        JP NZ,failed
        RET
checked_fcb:
        CALL 5
        CP 255
        JP Z,failed
        RET
failed: LD A,0xFF
        LD (0x8004),A
failure_loop: JP failure_loop
next: DW 0
current: DW 0
old_byte: DB 0
new_byte: DB 0
records: DW 0,1,3,4,31,32,127,128,255,256,511,512,599,0xFFFF
c_fcb: DB 3
        DEFM "EDGE    DAT"
        DS 24
d_fcb: DB 4
        DEFM "EDGE    DAT"
        DS 24

        DB 0                    ; materialise trailing FCB zero workspace
