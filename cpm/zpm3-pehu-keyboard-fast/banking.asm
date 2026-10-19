; SPDX-License-Identifier: GPL-3.0-or-later
; All three gateways fit the CP/M3 reserved003B-004F range. DI and stack
; operations are in high RAM before mapping; low gateways never touch SP.
install_helper:
        LD HL,helper_image
        LD DE,0x3B
        LD BC,19
        LDIR
        RET
helper_image:
        DB 0xD3,0xE3,0x7E,0xD3,0xE1,0xC9
        DB 0xD3,0xE3,0x77,0xD3,0xE1,0xC9
        DB 0xD3,0xE3,0xED,0xB0,0xD3,0xE1,0xC9
; Scanner callers use keyboard_safe_call: IRQs masked, native private stack,
; and one E3/E1 window around the entire original scanner invocation.
mmio_write:
        LD (HL),A
        RET
mmio_read:
        LD A,(HL)
        RET
mmio_copy:
        PUSH AF
        LDIR
        POP AF
        RET
