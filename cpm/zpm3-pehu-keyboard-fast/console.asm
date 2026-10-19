; SPDX-License-Identifier: GPL-3.0-or-later
; Keep the attributes initialised by the Sharp ROM; no BIOS colour choice.
; Native banked SUC VRAM, original Sharp font, software cursor and scroll.
console_init:
        XOR A
        LD (escape_state),A
        LD (terminal_error),A
        LD (cursor_drawn),A
        LD A,1
        LD (cursor_visible),A
        LD C,26

console_output:
        LD (video_saved_sp),SP
        LD SP,video_stack_end
        PUSH BC
        PUSH DE
        PUSH HL
        OUT (0xE3),A
        CALL hide_cursor
        LD A,C
        CALL output_character
        CALL cursor_tick
        OUT (0xE1),A
        POP HL
        POP DE
        POP BC
        LD SP,(video_saved_sp)
        RET

output_character:
        LD D,A
        LD A,(escape_state)
        OR A
        LD A,D
        JP NZ,escape_character
        CP 27
        JR Z,begin_escape
        CP 12                   ; form feed
        JP Z,clear_screen
        CP 26                   ; ADM3A clear
        JP Z,clear_screen
        CP 13
        JR Z,carriage_return
        CP 10
        JP Z,line_feed
        CP 8
        JR Z,backspace
        CP 127
        JR Z,backspace
        CP 9
        JR Z,tab
        CP 30                   ; ADM3A home
        JP Z,home
        CP 32
        RET C                   ; other controls, including BEL, ignored
        PUSH AF
        CALL screen_address
        POP AF
        CALL draw_character
        LD A,(cursor_column)
        INC A
        CP 80
        JR Z,wrap_line
        LD (cursor_column),A
        RET
begin_escape:
        LD A,1
        LD (escape_state),A
        RET
carriage_return:
        XOR A
        LD (cursor_column),A
        RET
backspace:
        LD A,(cursor_column)
        OR A
        RET Z
        DEC A
        LD (cursor_column),A
        RET
wrap_line:
        XOR A
        LD (cursor_column),A
line_feed:
        LD A,(cursor_row)
        INC A
        CP 25
        JR Z,scroll_up
        LD (cursor_row),A
        RET
scroll_up:
        ; Two alternating character halves, and matching attribute halves.
        LD HL,0xD028
        LD DE,0xD000
        LD BC,960
        CALL video_copy
        LD HL,0xD429
        LD DE,0xD401
        LD BC,960
        CALL video_copy
        LD HL,0xD828
        LD DE,0xD800
        LD BC,960
        CALL video_copy
        LD HL,0xDC29
        LD DE,0xDC01
        LD BC,960
        CALL video_copy
        LD HL,1920
        LD BC,80
        JP blank_cells

tab:
        LD A,(cursor_column)
        AND 7
        LD B,A
        LD A,8
        SUB B
        LD B,A
next_tab_space:
        PUSH BC
        LD A,32
        CALL output_character
        POP BC
        DJNZ next_tab_space
        RET

home:
        XOR A
        LD (cursor_column),A
        LD (cursor_row),A
        RET
clear_screen:
        CALL home
        XOR A
        LD (cursor_drawn),A
        LD HL,0xD000
        LD (HL),A
        LD DE,0xD001
        LD BC,2047
        JP video_copy
clear_eol:
        CALL logical_position
        PUSH HL
        LD A,(cursor_column)
        LD B,A
        LD A,80
        SUB B
        LD C,A
        LD B,0
        POP HL
        JP blank_cells
clear_eos:
        CALL logical_position
        PUSH HL
        EX DE,HL
        LD HL,2000
        OR A
        SBC HL,DE
        LD B,H
        LD C,L
        POP HL
blank_cells:
        LD A,B
        OR C
        RET Z
        PUSH HL
        ADD HL,BC
        EX (SP),HL              ; save logical end, retain logical start
        PUSH HL
        PUSH BC
        BIT 0,L
        JR NZ,blank_even_length
        INC BC
blank_even_length:
        SRL B
        RR C                    ; number of even logical cells
        SRL H
        RR L
        JR NC,blank_even_start
        INC HL
blank_even_start:
        LD DE,0xD000
        ADD HL,DE
        CALL zero_run
        POP BC
        POP HL
        BIT 0,L
        JR Z,blank_odd_length
        INC BC
blank_odd_length:
        SRL B
        RR C                    ; number of odd logical cells
        SRL H
        RR L
        INC HL
        LD DE,0xD400
        ADD HL,DE
        CALL zero_run
        POP HL                  ; original logical end and BC=0
        XOR A
        RET
zero_run:
        LD A,B
        OR C
        RET Z
        XOR A
        LD (HL),A
        DEC BC
        LD A,B
        OR C
        RET Z
        LD D,H
        LD E,L
        INC DE
        JP video_copy

; VT52 ESC A/B/C/D/H/E/J/K/Y, ADM3A ESC= row+32 col+32.
escape_character:
        LD A,(escape_state)
        CP 2
        JR Z,address_row
        CP 3
        JR Z,address_column
        XOR A
        LD (escape_state),A
        LD A,D
        CP 0x59
        JR Z,address_begin
        CP 0x3d
        JR Z,address_begin
        CP 0x45
        JP Z,clear_screen
        CP 0x48
        JP Z,home
        CP 0x4a
        JP Z,clear_eos
        CP 0x4b
        JP Z,clear_eol
        CP 0x41
        JR Z,cursor_up
        CP 0x42
        JR Z,cursor_down
        CP 0x43
        JR Z,cursor_right
        CP 0x44
        JP Z,backspace
        CP 0x65
        JR Z,cursor_on
        CP 0x66
        JR Z,cursor_off
        RET
address_begin:
        LD A,2
        LD (escape_state),A
        RET
address_row:
        LD A,D
        SUB 32
        JR C,bad_row
        CP 25
        JR C,row_ok
bad_row:
        XOR A
row_ok:
        LD (cursor_row),A
        LD A,3
        LD (escape_state),A
        RET
address_column:
        LD A,D
        SUB 32
        JR C,bad_column
        CP 80
        JR C,column_ok
bad_column:
        XOR A
column_ok:
        LD (cursor_column),A
        XOR A
        LD (escape_state),A
        RET
cursor_up:
        LD A,(cursor_row)
        OR A
        RET Z
        DEC A
        LD (cursor_row),A
        RET
cursor_down:
        LD A,(cursor_row)
        CP 24
        RET Z
        INC A
        LD (cursor_row),A
        RET
cursor_right:
        LD A,(cursor_column)
        CP 79
        RET Z
        INC A
        LD (cursor_column),A
        RET
cursor_on:
        LD A,1
        LD (cursor_visible),A
        RET
cursor_off:
        XOR A
        LD (cursor_visible),A
        RET

; Row/column logical index, without touching the CRTC or CPU memory map.
logical_position:
        LD A,(cursor_row)
        ADD A,A
        LD E,A
        LD D,0
        LD HL,row_offsets
        ADD HL,DE
        LD E,(HL)
        INC HL
        LD D,(HL)
        EX DE,HL                ; row*80, no table alignment requirement
add_column:
        LD A,(cursor_column)
        LD E,A
        LD D,0
        ADD HL,DE
        RET
screen_address:
        CALL logical_position
; Logical 0,1,2,3 -> D000,D401,D001,D402. Carry is the odd half.
physical_address_screen:
        SRL H
        RR L
        LD DE,0xD000
        JR NC,screen_even
        INC HL
        LD DE,0xD400
screen_even:
        ADD HL,DE
        RET
; HL=physical char cell, A=CP/M byte. The original SUC table maps the
; complete byte repertoire into the Sharp character generator codes.
draw_character:
        PUSH HL
        LD E,A
        LD D,0
        LD HL,suc_F3D6
        ADD HL,DE
        LD A,(HL)
        POP HL
        LD (HL),A
        RET
hide_cursor:
        LD A,(cursor_drawn)
        OR A
        RET Z
        LD HL,(cursor_address)
        LD A,(cursor_saved_character)
        LD (HL),A
        XOR A
        LD (cursor_drawn),A
        RET
update_cursor:
        LD (video_saved_sp),SP
        LD SP,video_stack_end
        PUSH AF
        PUSH BC
        PUSH DE
        PUSH HL
        OUT (0xE3),A
        CALL cursor_tick
        OUT (0xE1),A
        POP HL
        POP DE
        POP BC
        POP AF
        LD SP,(video_saved_sp)
        RET
cursor_tick:
        LD A,(cursor_visible)
        OR A
        JP Z,hide_cursor
        LD HL,0xE002
        LD A,(HL)
        BIT 6,A                 ; Sharp556 blink output; zero displays cursor
        JP NZ,hide_cursor
        LD A,(cursor_drawn)
        OR A
        RET NZ                  ; do not save our own glyph over the character
        CALL screen_address
        LD (cursor_address),HL
        LD A,(HL)
        LD (cursor_saved_character),A
        LD A,0xEF               ; original1Z-013A cursor display glyph
        LD (HL),A
        LD A,1
        LD (cursor_drawn),A
        RET
video_write:
        LD (HL),A
        RET
video_read:
        LD A,(HL)
        RET
video_copy:
        PUSH AF
        LD A,C
        AND 15
        JR Z,video_copy_bulk
video_copy_tail:
        LDI
        DEC A
        JR NZ,video_copy_tail
        LD A,B
        OR C
        JR Z,video_copy_done
video_copy_bulk:
        LDI
        LDI
        LDI
        LDI
        LDI
        LDI
        LDI
        LDI
        LDI
        LDI
        LDI
        LDI
        LDI
        LDI
        LDI
        LDI
        JP PE,video_copy_bulk
video_copy_done:
        POP AF
        RET
; Row lookup changes S/Z/PV relative to the arithmetic prefix. Every caller
; overwrites those flags (SRL/RR, SUB or OR) before a conditional use.
row_offsets:
        DW 0,80,160,240,320,400,480,560,640,720,800,880,960
        DW 1040,1120,1200,1280,1360,1440,1520,1600,1680,1760,1840,1920
video_saved_sp: DW 0
video_stack: DS 96
video_stack_end:
cursor_row: DB 0
cursor_column: DB 0
escape_state: DB 0
terminal_error: DB 0
cursor_visible: DB 1
cursor_drawn: DB 0
cursor_address: DW 0
cursor_saved_character: DB 0
console_end: DB 0
