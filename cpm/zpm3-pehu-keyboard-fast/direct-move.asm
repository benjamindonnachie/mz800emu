; PEHU MOVE: map source and destination physical 8KiB pages into CPU
; windows2000/4000 and copy directly. Code/state stays above6000 in bank0;
; common gateway provides shared stack, DI and forced caller-map restoration.
; BC=count,DE=source,HL=destination. Return BC=0 and advanced DE/HL.
; Forward byte semantics also hold for physically aliased/shared pages.
direct_move:
        LD (copy_destination),HL
        LD (copy_source),DE
        LD (copy_remaining),BC
        LD A,(COMMON_MOVE_PENDING)
        OR A
        JR NZ,copy_banks_ready
        LD A,(COMMON_CALLER_BANK)
        LD (COMMON_MOVE_SOURCE),A
        LD (COMMON_MOVE_DEST),A
copy_banks_ready:
        XOR A
        LD (COMMON_MOVE_PENDING),A
        LD A,B
        OR C
        RET Z
copy_page:
        LD HL,(copy_source)
        LD A,(COMMON_MOVE_SOURCE)
        CALL copy_page_number
        LD BC,0x20E7
        OUT (C),A
        SET 5,H
        LD (copy_source_alias),HL
        LD HL,(copy_destination)
        LD A,(COMMON_MOVE_DEST)
        CALL copy_page_number
        LD BC,0x40E7
        OUT (C),A
        SET 6,H
        LD (copy_destination_alias),HL
        ; Each copy chunk stops at both logical page boundaries and count end.
        LD HL,0x4000
        LD DE,(copy_source_alias)
        OR A
        SBC HL,DE
        LD B,H
        LD C,L
        LD HL,0x6000
        LD DE,(copy_destination_alias)
        OR A
        SBC HL,DE
        CALL copy_minimum
        LD HL,(copy_remaining)
        CALL copy_minimum
        LD (copy_chunk),BC
        LD HL,(copy_source_alias)
        LD DE,(copy_destination_alias)
        LD A,C
        AND 15
        JR Z,copy_unrolled
copy_tail:
        LDI
        DEC A
        JR NZ,copy_tail
        LD A,B
        OR C
        JR Z,copy_chunk_done
copy_unrolled:
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
        JP PE,copy_unrolled
copy_chunk_done:
        LD BC,(copy_chunk)
        LD HL,(copy_source)
        ADD HL,BC
        LD (copy_source),HL
        LD HL,(copy_destination)
        ADD HL,BC
        LD (copy_destination),HL
        LD HL,(copy_remaining)
        OR A
        SBC HL,BC
        LD (copy_remaining),HL
        LD A,H
        OR L
        JP NZ,copy_page
        LD HL,(copy_destination)
        LD DE,(copy_source)
        LD BC,0
        RET
; Return smaller of BC and HL in BC. HL/AF destroyed.
copy_minimum:
        OR A
        SBC HL,BC
        RET NC
        ADD HL,BC
        LD B,H
        LD C,L
        RET
; A=logical bank0/1,HL=logical address. Return physical page in A,
; offset0..1FFF in HL. Low page0 and upper pages6/7 are shared.
copy_page_number:
        LD D,A
        LD A,H
        RLCA
        RLCA
        RLCA
        AND 7
        JR Z,copy_shared_page
        CP 6
        JR NC,copy_shared_page
        LD E,A
        LD A,D
        AND 1
        RLCA
        RLCA
        RLCA
        OR E
copy_shared_page:
        LD E,A
        LD A,H
        AND 31
        LD H,A
        LD A,E
        RET
copy_source: DW 0
copy_destination: DW 0
copy_remaining: DW 0
copy_chunk: DW 0
copy_source_alias: DW 0
copy_destination_alias: DW 0
