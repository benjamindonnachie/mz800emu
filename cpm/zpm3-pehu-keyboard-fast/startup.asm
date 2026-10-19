; Identify the active OS without altering the original DRI loader credit.
startup_banner:
        LD HL,startup_text
startup_next:
        LD A,(HL)
        OR A
        RET Z
        LD C,A
        CALL console_output
        INC HL
        JR startup_next
startup_text:
        DB 13,10
        DEFM "ZPM3 N10 / ZCCP - PEHU, native512, GIDE RTC"
        DB 13,10,0
