; SPDX-License-Identifier: GPL-3.0-or-later
; Original SUC scanner, debounce/repeat, ALPHA, GRAPH, macros and controls.
; It has its own stack, like the original BIOS, with no original RAM address
; reservations. State/macro tables are relocated into the high native BIOS.
keyboard_init:
        CALL install_helper
        LD HL,suc_state
        LD (HL),0
        LD DE,suc_state+1
        LD BC,47
        LDIR
        LD HL,suc_state+2
        LD (HL),0xFF
        LD DE,suc_state+3
        LD BC,19
        LDIR
        LD A,0x80
        LD (suc_state+22),A
        LD A,0xFF
        LD (suc_state+29),A
        RET
console_status:
        CALL update_cursor      ; service hardware-timed blink while waiting
        PUSH HL
        LD HL,suc_F0A0
        CALL keyboard_safe_call
        POP HL
        RET
console_input:
        CALL console_status
        OR A
        JR Z,console_input
        PUSH HL
        LD HL,suc_F08D
        CALL keyboard_safe_call
        POP HL
        RET
keyboard_safe_call:
        LD (keyboard_target+1),HL
        PUSH BC
        PUSH DE
        PUSH HL
        LD A,I
        PUSH AF
        DI
        LD (keyboard_saved_sp),SP
        LD SP,keyboard_stack_end
        OUT (0xE3),A
keyboard_target:
        CALL 0
        OUT (0xE1),A
        LD SP,(keyboard_saved_sp)
        LD (keyboard_result),A
        POP AF
        JP PO,keyboard_irq_off
        POP HL
        POP DE
        POP BC
        LD A,(keyboard_result)
        EI
        RET
keyboard_irq_off:
        POP HL
        POP DE
        POP BC
        LD A,(keyboard_result)
        RET
keyboard_saved_sp: DW 0
keyboard_result: DB 0
keyboard_stack: DS 192
keyboard_stack_end: DB 0
