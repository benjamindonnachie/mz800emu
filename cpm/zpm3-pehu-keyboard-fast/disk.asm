; SPDX-License-Identifier: GPL-3.0-or-later
; Native fixed-disk driver adapted from cpm/gide/resident.asm.
select:
        LD A,C
        CP 2
        JR Z,select_c
        CP 3
        JR Z,select_d
        LD HL,0
        RET
select_c:
        LD A,1
        LD HL,dph_c
        JR select_hd
select_d:
        LD A,2
        LD HL,dph_d
select_hd:
        PUSH AF
        PUSH HL
        LD A,0xE0
        OUT (0xAE),A
        CALL ata_idle
        POP HL
        JR C,select_failed
        POP AF
        LD (active),A
        RET
select_failed:
        POP AF
        LD HL,0                   ; leave the previous active device intact
        RET

disk_home:
        LD BC,0
set_track:
        LD (track),BC
        RET
set_dma:
        LD (dma_address),BC
        RET

set_sector:
        LD (physical_sector),BC
        RET

read:
        CALL physical_address
        JR C,io_error
        CALL ata_read
        JR C,io_error
        XOR A
        RET
write:
        CALL physical_address
        JR C,io_error
        CALL ata_write
        JR C,io_error
        XOR A
        RET
io_error:
        LD A,1
        RET

; SETSEC supplies physical sector 0..31. DPB SPT remains 128 records.
; C/D retain the existing 8MiB on-disk layout without conversion.
physical_address:
        LD HL,(track)
        LD A,H
        CP 2
        JR NC,address_error
        LD A,(physical_sector+1)
        OR A
        JR NZ,address_error
        LD A,(physical_sector)
        CP 32
        JR NC,address_error
        ADD HL,HL
        ADD HL,HL
        ADD HL,HL
        ADD HL,HL
        ADD HL,HL
        LD E,A
        LD D,0
        ADD HL,DE
        LD A,(active)
        CP 2
        JR NZ,address_c
        SET 6,H
address_c:
        LD (lba),HL
        OR A
        RET
address_error:
        SCF
        RET

; Bounded polling: C flag means failure. Alternate status preserves GIDE LH.
ata_idle:
        LD BC,0x8000
idle_loop:
        IN A,(0xA6)
        CP 0xFF
        JR Z,ata_error
        OR A
        JR Z,ata_error
        AND 0xC8
        CP 0x40
        RET Z
        DEC BC
        LD A,B
        OR C
        JR NZ,idle_loop
ata_error:
        SCF
        RET
ata_drq:
        LD BC,0x8000
wait_loop:
        IN A,(0xA6)
        CP 0xFF
        JR Z,ata_error
        OR A
        JR Z,ata_error
        BIT 7,A
        JR NZ,wait_again
        AND 0x29                  ; DF, DRQ, ERR
        CP 8
        RET Z
        AND 0x21
        JR NZ,ata_error
wait_again:
        DEC BC
        LD A,B
        OR C
        JR NZ,wait_loop
        JR ata_error
issue:
        PUSH AF
        CALL ata_idle
        JR C,issue_error
        LD A,0xE0
        OUT (0xAE),A               ; master, LBA28
        LD A,1
        OUT (0xAA),A
        LD HL,(lba)
        LD A,L
        OUT (0xAB),A
        LD A,H
        OUT (0xAC),A
        XOR A
        OUT (0xAD),A
        POP AF
        OUT (0xAF),A               ; task register establishes low-byte phase
        JP ata_drq
issue_error:
        POP AF
        SCF
        RET
ata_read:
        LD A,0x20
        CALL issue
        RET C
        LD HL,(dma_address)
        CALL COMMON_TO_DMA
        JR transfer_done
ata_write:
        LD A,0x30
        CALL issue
        RET C
        LD HL,(dma_address)
        CALL COMMON_FROM_DMA
        CALL ata_idle
        RET C
transfer_done:
        IN A,(0xAF)
        AND 0xA9                  ; BSY, DF, DRQ, ERR must all be clear
        RET Z
        SCF
        RET

; Native512 banked CP/M3 structures. Buffers are owned by the BDOS BCB
; manager, not a private GIDE cache. All four buffers are in system bank0.
track: DW 0
dma_address: DW 0x80
active: DB 0
lba: DW 0
physical_sector: DW 0
dph_c: DW 0,0,0,0,0
        DB 0,0
        DW dpb,0,allocation_c,dir_root_c,data_root_c,0xFFFF
        DB 0
dph_d: DW 0,0,0,0,0
        DB 0,0
        DW dpb,0,allocation_d,dir_root_d,data_root_d,0xFFFF
        DB 0
dpb: EQU 0xD7D7
allocation_c: EQU 0xD8D8
allocation_d: EQU 0xD9D9
dir_root_c: DW dir_bcb_c
dir_root_d: DW dir_bcb_d
data_root_c: DW data_bcb_c
data_root_d: DW data_bcb_d
dir_bcb_c: DB 0xFF,0,0,0,0,0
        DW 0,0,directory_buffer
        DB 0
        DW 0
dir_bcb_d: DB 0xFF,0,0,0,0,0
        DW 0,0,directory_buffer_d
        DB 0
        DW 0
data_bcb_c: DB 0xFF,0,0,0,0,0
        DW 0,0,data_buffer_c
        DB 0
        DW 0
data_bcb_d: DB 0xFF,0,0,0,0,0
        DW 0,0,data_buffer_d
        DB 0
        DW 0
directory_buffer: DS 512
directory_buffer_d: DS 512
data_buffer_c: DS 512
data_buffer_d: DS 512
resident_end: DB 0
bank_test_area: DS 64
high_stack_base: DS 64
high_stack_end: DB 0
