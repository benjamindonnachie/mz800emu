; Loaded normally through CCP, same binary on both operating systems.
; Boundaries are debugger breakpoints: no host pacing or keyboard in timing.
        ORG 0x100
        LD SP,0x7000
        LD HL,(6)
        LD L,0
        LD (0x8000),HL
        LD HL,0x4001             ; deliberately unaligned logical DMA
        LD B,128
        XOR A
fill:   LD (HL),A
        INC A
        INC HL
        DJNZ fill
read_start:
        LD DE,input_fcb
        LD C,15
        CALL 5
        CP 255
        JP Z,failed
        LD HL,600
        LD (remaining),HL
read_loop:
        LD DE,0x4001
        LD C,26
        CALL 5
        LD DE,input_fcb
        LD C,20
        CALL 5
        OR A
        JP NZ,failed
        LD HL,0x4001
        LD B,128
        XOR A
verify: CP (HL)
        JP NZ,failed
        INC A
        INC HL
        DJNZ verify
        CALL next_record
        JR NZ,read_loop
        LD DE,input_fcb
        LD C,16
        CALL 5
        CP 255
        JP Z,failed
read_end:
        NOP
write_start:
        LD DE,output_fcb
        LD C,22
        CALL 5
        CP 255
        JP Z,failed
        LD HL,600
        LD (remaining),HL
write_loop:
        LD DE,0x4001
        LD C,26
        CALL 5
        LD DE,output_fcb
        LD C,21
        CALL 5
        OR A
        JP NZ,failed
        CALL next_record
        JR NZ,write_loop
        LD DE,output_fcb
        LD C,16
        CALL 5
        CP 255
        JP Z,failed
        LD E,0
        LD C,48                 ; include explicit BDOS flush in timing
        CALL 5
        OR A
        JP NZ,failed
write_end:
        LD E,27
        CALL emit
        LD E,102                ; VT52 cursor off, avoid blink-phase variance
        CALL emit
        LD E,26
        CALL emit
print_start:
        LD BC,1000
print_loop:
        PUSH BC
        LD E,65
        CALL emit
        POP BC
        DEC BC
        LD A,B
        OR C
        JR NZ,print_loop
print_end:
        NOP
erase_start:
        LD B,10
erase_loop:
        PUSH BC
        LD E,27
        CALL emit
        LD E,89                 ; VT52 address row0, column1
        CALL emit
        LD E,32
        CALL emit
        LD E,33
        CALL emit
        LD E,27
        CALL emit
        LD E,74                 ; erase1999 cells, both SUC halves
        CALL emit
        POP BC
        DJNZ erase_loop
erase_end:
        NOP
        LD E,27
        CALL emit
        LD E,89
        CALL emit
        LD E,56                 ; bottom row24, column0
        CALL emit
        LD E,32
        CALL emit
scroll_start:
        LD B,100
scroll_loop:
        PUSH BC
        LD E,10                 ; each line feed scrolls the full display
        CALL emit
        POP BC
        DJNZ scroll_loop
scroll_end:
        NOP
clear_start:
        LD B,100
clear_loop:
        PUSH BC
        LD E,26
        CALL emit
        POP BC
        DJNZ clear_loop
clear_end:
        LD A,0xA5
        LD (0x8004),A
done:   JP done
emit:   LD C,6
        CALL 5
        RET
next_record:
        LD HL,(remaining)
        DEC HL
        LD (remaining),HL
        LD A,H
        OR L
        RET
failed: LD A,0xFF
        LD (0x8004),A
failure_loop: JP failure_loop
remaining: DW 0
input_fcb: DB 3
        DEFM "BENCHIN DAT"
        DS 24
output_fcb: DB 3
        DEFM "BENCHOUTDAT"
        DS 24

        DB 0                    ; force trailing FCB workspace into COM
