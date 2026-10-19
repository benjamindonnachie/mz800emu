; SPDX-License-Identifier: GPL-3.0-or-later
; RTC [YYYY-MM-DD HH:MM[:SS]], CP/M3 banked PEHU GIDE RTC BIOS.
        ORG 0x100
start:
        LD A,(0x80)
        OR A
        JP Z,display
        LD HL,0x81
        CALL spaces
        OR A
        JP Z,display
        CP 13
        JP Z,display
        CALL parse_two
        CP 19
        JR Z,century19
        CP 20
        JP NZ,error
        LD A,100
        JR century_ready
century19:
        XOR A
century_ready:
        LD (century),A
        CALL parse_two
        LD B,A
        LD A,(century)
        ADD A,B
        CP 78
        JP C,error
        CP 178
        JP NC,error
        LD (human),A
        LD A,45
        CALL separator
        CALL parse_two
        OR A
        JP Z,error
        CP 13
        JP NC,error
        LD (human+1),A
        LD A,45
        CALL separator
        CALL parse_two
        OR A
        JP Z,error
        CP 32
        JP NC,error
        LD (human+2),A
        LD A,32
        CALL separator
        CALL spaces
        CALL parse_two
        CP 24
        JP NC,error
        LD (human+3),A
        LD A,58
        CALL separator
        CALL parse_two
        CP 60
        JP NC,error
        LD (human+4),A
        XOR A
        LD (human+5),A
        LD A,(HL)
        CP 58
        JR NZ,seconds_ready
        INC HL
        CALL parse_two
        CP 60
        JP NC,error
        LD (human+5),A
seconds_ready:
        CALL spaces
        OR A
        JR Z,command_ready
        CP 13
        JP NZ,error
command_ready:
        LD A,(human)
        LD B,A
        LD A,(human+1)
        LD C,A
        LD A,(human+2)
        CALL to_day
        LD (stamp),HL
        CALL to_calendar
        LD D,A
        LD A,(human)
        CP B
        JP NZ,error
        LD A,(human+1)
        CP C
        JP NZ,error
        LD A,(human+2)
        CP D
        JP NZ,error
        LD A,(human+3)
        CALL bcd
        LD (stamp+2),A
        LD A,(human+4)
        CALL bcd
        LD (stamp+3),A
        LD A,(human+5)
        CALL bcd
        LD (second_parameter+2),A
        LD DE,stamp
        LD C,104
        CALL 5
        LD DE,second_parameter
        LD C,49
        CALL 5
        LD DE,time_parameter
        LD C,50
        CALL 5
        ; Invalidate the SCB day first: GET must refresh it from actual hardware.
        LD DE,probe_parameter
        LD C,49
        CALL 5
        LD DE,stamp
        LD C,105
        CALL 5
        LD (stamp+4),A
        LD HL,(stamp)
        LD A,H
        OR L
        JP Z,unavailable
        LD DE,36526
        OR A
        SBC HL,DE
        JP NC,unavailable
        ADD HL,DE
        CALL to_calendar
        LD D,A
        LD A,(human)
        CP B
        JP NZ,unavailable
        LD A,(human+1)
        CP C
        JP NZ,unavailable
        LD A,(human+2)
        CP D
        JP NZ,unavailable
        JR display_ready

display:
        LD DE,stamp
        LD C,105
        CALL 5
        LD (stamp+4),A
        LD HL,(stamp)
        LD A,H
        OR L
        JP Z,unavailable
        LD DE,36526
        OR A
        SBC HL,DE
        JP NC,unavailable
        ADD HL,DE
        CALL to_calendar
        LD D,A
display_ready:
        LD A,D
        LD (display_day),A
        LD A,B
        CP 100
        JR C,print19
        LD A,50
        CALL character
        LD A,48
        CALL character
        LD A,B
        SUB 100
        JR print_year
print19:
        LD A,49
        CALL character
        LD A,57
        CALL character
        LD A,B
print_year:
        CALL decimal_two
        LD A,45
        CALL character
        LD A,C
        CALL decimal_two
        LD A,45
        CALL character
        LD A,(display_day)
        CALL decimal_two
        LD A,32
        CALL character
        LD A,(stamp+2)
        CALL bcd_two
        LD A,58
        CALL character
        LD A,(stamp+3)
        CALL bcd_two
        LD A,58
        CALL character
        LD A,(stamp+4)
        CALL bcd_two
        LD A,13
        CALL character
        LD A,10
        CALL character
        JP 0
spaces:
        LD A,(HL)
        CP 32
        RET NZ
        INC HL
        JR spaces
separator:
        CP (HL)
        JP NZ,error
        INC HL
        RET
parse_two:
        LD A,(HL)
        SUB 48
        CP 10
        JP NC,error
        LD D,A
        ADD A,A
        ADD A,A
        ADD A,D
        ADD A,A
        LD D,A
        INC HL
        LD A,(HL)
        SUB 48
        CP 10
        JP NC,error
        ADD A,D
        INC HL
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
bcd_two:
        PUSH BC
        LD B,A
        RRCA
        RRCA
        RRCA
        RRCA
        AND 15
        ADD A,48
        CALL character
        LD A,B
        AND 15
        ADD A,48
        CALL character
        POP BC
        RET
decimal_two:
        LD E,0
decimal_tens:
        SUB 10
        JR C,decimal_units
        INC E
        JR decimal_tens
decimal_units:
        ADD A,10
        LD D,A
        LD A,E
        ADD A,48
        CALL character
        LD A,D
        ADD A,48
        JP character
character:
        PUSH AF
        PUSH BC
        PUSH DE
        PUSH HL
        LD E,A
        LD C,2
        CALL 5
        POP HL
        POP DE
        POP BC
        POP AF
        RET
error:
        LD DE,usage
        JR message
unavailable:
        LD DE,no_clock
message:
        LD C,9
        CALL 5
        JP 0
usage: DB 82,84,67,32,91,89,89,89,89,45,77,77,45,68,68,32,72,72,58,77,77,91,58,83,83,93,93,44,49,57,55,56,46,46,50,48,55,55,59,32,105,110,118,97,108,105,100,32,100,97,116,101,47,116,105,109,101,46,13,10,36
no_clock: DB 82,84,67,32,117,110,97,118,97,105,108,97,98,108,101,58,32,99,104,101,99,107,32,116,104,101,32,71,73,68,69,32,99,97,114,100,32,97,110,100,32,99,108,111,99,107,32,115,101,116,116,105,110,103,115,46,13,10,36
human: DS 6
century: DB 0
display_day: DB 0
stamp: DS 5
second_parameter: DB 0x5C,0xFF,0
probe_parameter: DB 0x58,0xFE,0xFF,0xFF
time_parameter: DB 26,0,0xFF,0,0,0,0,0

to_day:
        PUSH AF
        PUSH BC
        LD A,B
        SUB 76
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
        POP BC
        LD A,C
        CALL month_offset
        ADD HL,DE
        POP AF
        LD E,A
        LD D,0
        ADD HL,DE
        DEC HL
        RET
to_calendar:
        LD DE,730
        ADD HL,DE
        LD B,76
        LD DE,1461
quarters:
        OR A
        SBC HL,DE
        JR C,quarter_remainder
        LD A,B
        ADD A,4
        LD B,A
        JR quarters
quarter_remainder:
        ADD HL,DE
        LD DE,366
years:
        OR A
        SBC HL,DE
        JR C,year_remainder
        INC B
        LD DE,365
        JR years
year_remainder:
        ADD HL,DE
        LD A,12
months:
        CALL month_offset
        OR A
        SBC HL,DE
        JR NC,day_remainder
        ADD HL,DE
        DEC A
        JR months
day_remainder:
        LD C,A
        LD A,L
        INC A
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
calendar_end:
