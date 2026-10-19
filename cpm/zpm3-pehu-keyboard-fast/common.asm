; SPDX-License-Identifier: GPL-3.0-or-later
; Common BIOS for stock banked DRI BDOS. Low 8 KiB and upper 16 KiB
; are shared; windows 2000-BFFF switch between system0 and application1.
bios_vectors:
        JP cold_boot
        JP warm_boot
        JP g_const
        JP g_conin
        JP g_conout
        JP null
        JP null
        JP eof
        JP g_home
        JP g_select
        JP g_track
        JP g_sector
        JP g_dma
        JP g_read
        JP g_write
        JP yes
        JP sectrn
        JP yes
        JP yes
        JP yes
        JP devtbl
        JP null
        JP drvtbl
        JP null
        JP flush
        JP move
        JP g_time
        JP selmem
        JP setbnk
        JP xmove
        JP null
        JP null
        JP null
null:   RET
yes:    LD A,255
        RET
eof:    LD A,26
        RET
flush:  XOR A
        RET
devtbl: LD HL,0xFFFF
        RET
drvtbl: LD HL,0xFFFF
        RET
sectrn: LD H,B
        LD L,C
        RET
; Each thunk preserves input HL. Its target is a relocatable DSEG symbol.
g_const: PUSH HL
        LD HL,T_CONST
        JP gateway
g_conin: PUSH HL
        LD HL,T_CONIN
        JP gateway
g_conout: PUSH HL
        LD HL,T_CONOUT
        JP gateway
g_home: PUSH HL
        LD HL,T_HOME
        JP gateway
g_select: PUSH HL
        LD HL,T_SELECT
        JP gateway
g_track: PUSH HL
        LD HL,T_TRACK
        JP gateway
g_sector: PUSH HL
        LD HL,T_SECTOR
        JP gateway
g_dma:  PUSH HL
        LD HL,T_DMA
        JP gateway
g_read: PUSH HL
        LD HL,T_READ
        JP gateway
g_write: PUSH HL
        LD HL,T_WRITE
        JP gateway
g_time: PUSH HL
        LD HL,T_TIME
        JP gateway
; No stack access to an application page after changing its mapping.
; Non-reentrant gateway. IRQs are suspended through the native BIOS call.
gateway:
        LD (gate_call+1),HL
        POP HL
        LD (gate_saved_sp),SP
        LD SP,gate_stack_end
        PUSH AF
        LD A,I
        DI
        LD A,0
        JP PO,gate_irq_set
        LD A,0xFB
gate_irq_set:
        LD (gate_irq),A
        LD A,(current_bank)
        LD (gate_saved_bank),A
        XOR A
        CALL bank_force_masked
        POP AF
gate_call: CALL 0
        PUSH AF
        LD A,(gate_saved_bank)
        CALL bank_force_masked
        POP AF
        LD SP,(gate_saved_sp)
gate_irq: NOP
        RET

; SELMEM follows CP/M3: change execution bank and default DMA bank.
selmem:
        LD (dma_bank),A
bank_raw:
        PUSH AF
        PUSH BC
        LD B,A
        LD A,(current_bank)
        CP B
        JR NZ,bank_change
        POP BC
        POP AF
        RET
bank_force:
        PUSH AF
        PUSH BC
        LD B,A
bank_change:
        LD A,I
        PUSH AF
        DI
        LD A,B
        AND 1
        LD (current_bank),A
        OR A
        LD A,1
        JR Z,map_first
        LD A,9
map_first:
        LD BC,0x20E7
        OUT (C),A
        INC A
        LD B,0x40
        OUT (C),A
        INC A
        LD B,0x60
        OUT (C),A
        INC A
        LD B,0x80
        OUT (C),A
        INC A
        LD B,0xA0
        OUT (C),A
        POP AF
        JP PO,bank_irq_off
        POP BC
        POP AF
        EI
        RET
bank_irq_off:
        POP BC
        POP AF
        RET
; Private gateway-only entry: DI is already in force and the shared stack
; is installed. Preserve AF/BC and force every page write, even when the
; logical bank matches current_bank (MOVE may have left temporary aliases).
; Duplicating this small body avoids both nested IFF bookkeeping and another
; CALL/RET. Public bank_raw/bank_force keep their interrupt-aware contract.
bank_force_masked:
        PUSH AF
        PUSH BC
        AND 1
        LD (current_bank),A
        OR A
        LD A,1
        JR Z,masked_map_first
        LD A,9
masked_map_first:
        LD BC,0x20E7
        OUT (C),A
        INC A
        LD B,0x40
        OUT (C),A
        INC A
        LD B,0x60
        OUT (C),A
        INC A
        LD B,0x80
        OUT (C),A
        INC A
        LD B,0xA0
        OUT (C),A
        POP BC
        POP AF
        RET
setbnk:
        LD (dma_bank),A
        RET
; DRI XMOVE convention: B=destination bank, C=source bank.
xmove:
        LD A,B
        LD (move_dest),A
        LD A,C
        LD (move_source),A
        LD A,1
        LD (move_pending),A
        RET
 ; MOVE executes in native bank0 above the two temporary alias windows.
move:
        PUSH HL
        LD HL,T_MOVE
        JP gateway
; Bulk ATA transfers run in common code while the requested DMA bank is
; selected. No intermediate BIOS sector buffer and no read-before-write.
to_dma:
        PUSH AF
        PUSH BC
        LD A,(current_bank)
        PUSH AF
        LD A,(dma_bank)
        CALL bank_raw
        LD A,2
        LD BC,0x00A8
ata_read_burst:
        INI
        INI
        INI
        INI
        INI
        INI
        INI
        INI
        INI
        INI
        INI
        INI
        INI
        INI
        INI
        INI
        JP NZ,ata_read_burst
        DEC A
        JR NZ,ata_read_burst
        JR ata_dma_return
from_dma:
        PUSH AF
        PUSH BC
        LD A,(current_bank)
        PUSH AF
        LD A,(dma_bank)
        CALL bank_raw
        LD A,2
        LD BC,0x00A8
ata_write_burst:
        OUTI
        OUTI
        OUTI
        OUTI
        OUTI
        OUTI
        OUTI
        OUTI
        OUTI
        OUTI
        OUTI
        OUTI
        OUTI
        OUTI
        OUTI
        OUTI
        JP NZ,ata_write_burst
        DEC A
        JR NZ,ata_write_burst
ata_dma_return:
        POP AF
        CALL bank_raw
        POP BC
        POP AF
        RET
cold_boot:
        DI
        LD SP,boot_stack_end
        XOR A
        LD (current_bank),A
        LD (dma_bank),A
        CALL bank_raw
        CALL T_KEYINIT
        LD C,0
        CALL g_time
        ; Adopt loader cursor, retaining monitor attributes and load map.
        LD HL,T_CURSOR
        LD DE,LOADER_CONSOLE
        LD BC,9
        CALL move
        CALL T_STARTUP
        JP warm_boot
warm_boot:
        DI
        LD SP,boot_stack_end
        LD A,1
        CALL selmem
        LD A,0xC3
        LD (0),A
        LD (5),A
        LD HL,bios_vectors+3
        LD (1),HL
        LD HL,(SCB_MXTPA)
        LD (6),HL
        ; Install low native MMIO gateways from system-bank code.
        LD HL,T_HELPER
        PUSH HL
        XOR A
        CALL bank_raw
        POP HL
        CALL jump_hl
        LD A,1
        CALL selmem
        ; CCP is a C0 system file; retain the caller's selected user.
        LD C,32
        LD E,0xFF
        CALL 5
        LD (warm_user),A
        LD C,32
        LD E,0
        CALL 5
        LD C,13
        CALL 5
        LD C,14
        LD DE,2
        CALL 5
        LD HL,0x5C
        LD DE,0x5D
        LD (HL),0
        LD BC,35
        LDIR
        LD A,3
        LD (0x5C),A
        LD HL,ccp_name
        LD DE,0x5D
        LD BC,11
        LDIR
        LD DE,0x5C
        LD C,15
        CALL 5
        CP 255
        JP Z,boot_error
        LD C,44
        LD DE,1
        CALL 5
        LD HL,0x100
load_ccp:
        PUSH HL
        EX DE,HL
        LD C,26
        CALL 5
        LD DE,0x5C
        LD C,20
        CALL 5
        POP HL
        OR A
        JR NZ,ccp_loaded
        LD DE,128
        ADD HL,DE
        JR load_ccp
ccp_loaded:
        CP 1
        JP NZ,boot_error
        LD A,(warm_user)
        LD E,A
        LD C,32
        CALL 5
        LD BC,0x0002
        JP 0x100
jump_hl:
        JP (HL)
boot_error:
        LD DE,error_text
        LD C,9
        CALL 5
        HALT
        JR boot_error
error_text: DEFM "PEHU BIOS: CCP load error$"
ccp_name: DEFM "CCP     COM"
warm_user: DB 0
current_bank: DB 0
dma_bank: DB 0
move_pending: DB 0
move_source: DB 0
move_dest: DB 0
gate_saved_bank: DB 0
gate_saved_sp: DW 0
gate_stack: DS 80
gate_stack_end: DB 0
boot_stack: DS 96
boot_stack_end: DB 0

; Banked DRI BDOS requires TWO256-byte allocation maps per drive.
; Public DPB and allocation-vector pointers returned by BDOS31/27 must
; remain readable after the resident BDOS restores the application bank.
public_dpb: DW 128
        DB 5,31,1
        DW 2047,511
        DB 0xF0,0
        DW 0x8000,0
        DB 2,3
public_alv_c: DS 512
public_alv_d: DS 512
        DB 0
