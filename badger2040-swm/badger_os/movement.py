##############################################################################
# Movement
##############################################################################
# Copyright (c) Simon W. Moore, November 2023
#
# Uses the PIO state machines on the Pico to monitor distance and velocity
# based on signals from the hub dynamo.

import rp2


class movement:
    # PIO program for dynamo input change counter (i.e. distance)
    # 12 instructions
    @rp2.asm_pio()
    def __pioctr():
        set(x, 0)
        wrap_target()
        ######## ctrstart
        label("ctrstart")
        mov(isr,x)
        push(noblock)
        wait(0,pin,0) [1]
        set(pins, 0)
        wait(1,pin,0) [1]
        set(pins, 1)
        jmp(x_dec, "ctrstart")
        wrap()

    # PIO program for dynamo input periodicity (i.e. velocity)
    # 14 instructions
    @rp2.asm_pio()
    def __pioperiod():
        pull(block) # receive time out value
        mov(y,osr)
        mov(isr,y)
        push(block)
        wrap_target()
        set(x, 0)
        wait(1,pin,0)
        ######## waitzero
        label("waitzero")    # Usual loop cycle count:
        jmp(x_not_y,"notA")  # 1
        jmp("timeout")
        ######## notA
        label("notA")
        jmp(pin,"stillone")  # 2
        jmp("waitone")
        ######## stillone
        label("stillone")
        jmp(x_dec, "decA")   # 3
        ######## decA
        label("decA")
        jmp("waitzero")      # 4
        ######## waitone
        label("waitone")
        jmp(x_not_y,"notB")  # 1
        jmp("timeout")
        ######## notB
        label("notB")
        jmp(pin,"finished")  # 2
        jmp(x_dec, "decB")   # 3
        ######## decB
        label("decB")
        jmp("waitone")       # 4
        ######## timeout
        label("timeout")
        set(x,2)
        ######## finished
        label("finished")
        mov(isr,x)
        push(noblock)
        wrap()
    
    def __sign_extend(value, bits):
        sign_bit = 1 << (bits - 1)
        return (value & (sign_bit - 1)) - (value & sign_bit)

    def distance_since_on():
        timeout = 4
        while((timeout>0) and (self.pioctrsm.rx_fifo()>0)):
            ctr = -self.__sign_extend(self.pioctrsm.get(),32)-1
            timeout = timeout-1
        return ctr * self.dist_per_pulse / 1000.0

    def velocity():
        timeout = 4
        while((timeout>0) and (self.pioperiodsm.rx_fifo()>0)):
            self.velocity_counter = -self.__sign_extend(self.pioperiodsm.get(),32)-1
            timeout = timeout-1
        return 0.0 if (self.velocity_counter < 0) else self.dist_per_pulse * 1000000.0 / self.velocity_counter

    def __init__(button,dist_per_pulse):
        self.dist_per_pulse = dist_per_pulse
        # okay to simplify?:  self.pioctrsm = rp2.StateMachine(0, self.__pioctr, in_base=button, jmp_pin=button, set_base=machine.Pin(badger2040.LED), freq=2000000)
        self.pioctrsm = rp2.StateMachine(0, self.__pioctr, in_base=button, jmp_pin=button, freq=2000000)
        self.pioctrsm.active(1)
        self.pioperiodsm = rp2.StateMachine(5, self.__pioperiod, in_base=button, jmp_pin=button, freq=4000000)
        self.pioperiodsm.active(1)
        period_timeout = 5000000
        self.pioperiodsm.put(-period_timeout)
        self.counter = 0
        # remove any stray FIFO entries (needed?)
        _ = self.distance()
        self.counter = 0
        _ = self.velocity()

