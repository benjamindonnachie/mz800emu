; SPDX-License-Identifier: GPL-3.0-or-later
; GIDE RTC72421. Existing validated calendar service now lives in PEHU bank0.
; No ROM mapping or low-RAM scratch: common BIOS gateway masks interrupts.
; TIME C=0 read, C=FF write. Preserve BC/DE/HL and caller interrupt state.
rtc_time:
        PUSH BC
        PUSH DE
        PUSH HL
        LD A,C
        PUSH AF
        LD HL,SCB_DATE
        LD DE,rtc_calendar
        LD BC,5
        LDIR
        POP AF
        CALL service
        JR C,rtc_finished
        OR A
        JR NZ,rtc_finished
        LD HL,rtc_calendar
        LD DE,SCB_DATE
        LD BC,5
        LDIR
rtc_finished:
        POP HL
        POP DE
        POP BC
        RET
rtc_calendar: DS 6
service:
        PUSH AF
        OR A                    ; HOLD success must return carry clear.
        CALL hold
        JP C,unavailable
        POP AF
        OR A
        JP NZ,set_time
        LD HL,rtc_calendar+5
        LD B,11
read_pair:
        IN A,(C)
        AND 15
        RLCA
        RLCA
        RLCA
        RLCA
        LD D,A
        DEC B
        IN A,(C)
        AND 15
        OR D
        LD (HL),A
        DEC HL
        DEC B
        JP P,read_pair
        LD BC,0x0FA5
        IN A,(C)
        BIT 2,A
        JR NZ,read_24
        LD A,(rtc_calendar+2)
        PUSH AF
        AND 0x3F
        CALL unbcd
        POP DE
        JP C,invalid
        CP 13
        JP NC,invalid
        CP 12
        JR NZ,am_hour
        XOR A
am_hour:
        BIT 6,D
        JR Z,store_hour
        ADD A,12
store_hour:
        CALL bcd
        LD (rtc_calendar+2),A
read_24:
        LD A,(rtc_calendar+5)
        CALL unbcd
        JP C,invalid
        CP 78
        JR NC,read_year_ready
        ADD A,100
read_year_ready:
        SUB 76
        LD B,A
        LD C,A
        LD L,A
        LD H,0
        LD E,A
        LD D,0
        ADD HL,HL
        ADD HL,HL
        ADD HL,HL
        ADD HL,DE
        ADD HL,HL
        ADD HL,HL
        ADD HL,HL
        ADD HL,DE
        LD D,H
        LD E,L
        ADD HL,HL
        ADD HL,HL
        ADD HL,DE
        LD A,C
        ADD A,3
        SRL A
        SRL A
        LD E,A
        LD D,0
        ADD HL,DE
        LD DE,-730
        ADD HL,DE
        LD A,(rtc_calendar+4)
        CALL unbcd
        JP C,invalid
        CP 1
        JP C,invalid
        CP 13
        JP NC,invalid
        LD C,A
        CALL month_offset
        ADD HL,DE
        LD A,E
        LD (rtc_calendar+4),A
        LD A,C
        INC A
        CALL month_offset
        LD A,(rtc_calendar+4)
        LD C,A
        LD A,E
        SUB C
        LD C,A
read_day:
        LD A,(rtc_calendar+3)
        CALL unbcd
        JP C,invalid
        OR A
        JP Z,invalid
        CP C
        JR Z,valid_day
        JP NC,invalid
valid_day:
        LD E,A
        LD D,0
        ADD HL,DE
        DEC HL
        LD A,(rtc_calendar)
        LD (rtc_calendar+4),A
        LD A,(rtc_calendar+1)
        LD (rtc_calendar+3),A
        LD (rtc_calendar),HL
        JP validate_time
unavailable:
        POP AF
        LD A,255
        SCF
        JP rom_exit
set_time:
        CALL check_time
        JP C,invalid
        LD HL,(rtc_calendar)
        LD A,H
        OR L
        JP Z,invalid
        LD DE,36526
        OR A
        SBC HL,DE
        JP NC,invalid
        ADD HL,DE
        DEC HL
        PUSH HL
        LD E,L
        LD L,H
        LD H,0
        ADD HL,HL
        ADD HL,HL
        LD D,0
        ADD HL,DE
        LD DE,7
weekday:
        OR A
        SBC HL,DE
        JR NC,weekday
        ADD HL,DE
        LD A,L
        LD BC,0x0CA5
        OUT (C),A
        POP HL
        LD A,(rtc_calendar+4)
        LD (rtc_calendar),A
        LD A,(rtc_calendar+3)
        LD (rtc_calendar+1),A
        LD DE,731
        ADD HL,DE
        LD B,76
        LD DE,1461
set_quarters:
        OR A
        SBC HL,DE
        JR C,set_quarter_remainder
        LD A,B
        ADD A,4
        LD B,A
        JR set_quarters
set_quarter_remainder:
        ADD HL,DE
        LD DE,366
set_year:
        OR A
        SBC HL,DE
        JR C,set_month_start
        INC B
        LD DE,365
        JR set_year
set_month_start:
        ADD HL,DE
        LD A,12
set_month:
        CALL month_offset
        OR A
        SBC HL,DE
        JR NC,set_day
        ADD HL,DE
        DEC A
        JR set_month
set_day:
        LD C,A
        LD A,L
        INC A
        CALL bcd
        LD (rtc_calendar+3),A
        LD A,C
        CALL bcd
        LD (rtc_calendar+4),A
        LD A,B
        CP 100
        JR C,set_year_digits
        SUB 100
set_year_digits:
        CALL bcd
        LD (rtc_calendar+5),A
        LD BC,0x0FA5
        LD A,5
        OUT (C),A
        LD A,4
        OUT (C),A
        LD HL,rtc_calendar+5
        LD B,11
write_pair:
        LD A,(HL)
        RRCA
        RRCA
        RRCA
        RRCA
        AND 15
        OUT (C),A
        DEC B
        LD A,(HL)
        AND 15
        OUT (C),A
        DEC HL
        DEC B
        JP P,write_pair
        LD A,255
        OR A
        JP release
validate_time:
        CALL check_time
        LD A,0
        JR release
check_time:
        LD HL,rtc_calendar+2
        LD B,3
        LD C,24
check_time_byte:
        LD A,(HL)
        CALL unbcd
        RET C
        CP C
        JR NC,bad_time
        INC HL
        LD C,60
        DJNZ check_time_byte
        OR A
        RET
bad_time:
        SCF
        RET
invalid:
        LD A,255
        SCF
release:
        PUSH AF
        LD BC,0x0DA5
        LD A,4
        OUT (C),A
        POP AF
rom_exit:
        RET
hold:
        LD BC,0x0DA5
        LD E,128
hold_retry:
        LD A,5
        OUT (C),A
        IN A,(C)
        BIT 1,A
        RET Z
        LD A,4
        OUT (C),A
        DEC E
        JR NZ,hold_retry
        SCF
        RET
month_offset:
        PUSH AF
        PUSH HL
        LD E,A
        LD D,0
        LD HL,month_offsets-1
        ADD HL,DE
        LD E,(HL)
        LD D,0
        CP 10
        JR C,month_high_ready
        INC D
month_high_ready:
        CP 3
        JR C,month_ready
        LD A,B
        AND 3
        JR NZ,month_ready
        INC DE
month_ready:
        POP HL
        POP AF
        RET
month_offsets:
        DB 0,31,59,90,120,151,181,212,243,17,48,78,109
unbcd:
        LD D,A
        AND 15
        CP 10
        JR NC,bad_bcd
        LD E,A
        LD A,D
        AND 0xF0
        RRCA
        RRCA
        RRCA
        RRCA
        CP 10
        JR NC,bad_bcd
        LD D,A
        ADD A,A
        ADD A,A
        ADD A,D
        ADD A,A
        ADD A,E
        OR A
        RET
bad_bcd:
        SCF
        RET
bcd:
        PUSH BC
        LD C,A
        XOR A
        LD B,8
bcd_digit:
        SLA C
        ADC A,A
        DAA
        DJNZ bcd_digit
        POP BC
        RET
service_end:
