#-----------------------------------------------------------------------------
# Movement - detect movement for Cycle Computer 2 using Pico PIO programs
#-----------------------------------------------------------------------------
# Copyright (c) Simon W. Moore, March 2024


import rp2

class Movement:
    def __sign_extend(self, value, bits):
        sign_bit = 1 << (bits - 1)
        return (value & (sign_bit - 1)) - (value & sign_bit)

    def distance_since_on(self):
        timeout = 4
        while((timeout>0) and (self.pioctrsm.rx_fifo()>0)):
            self.dist_ctr = -self.__sign_extend(self.pioctrsm.get(),32)-1
            timeout = timeout-1
        return self.dist_ctr * self.dist_per_pulse / 1000.0

    def velocity(self):
        timeout = 4
        while((timeout>0) and (self.pioperiodsm.rx_fifo()>0)):
            self.velocity_counter = -self.__sign_extend(self.pioperiodsm.get(),32)-1
            timeout = timeout-1
        return 0.0 if (self.velocity_counter < 0) else self.dist_per_pulse * 1000000.0 / self.velocity_counter

    def __init__(self,button,dist_per_pulse):
        # PIO program for dynamo input change counter (i.e. distance)
        # 12 instructions
        @rp2.asm_pio()
        def pioctr():
            set(x, 0)
            wrap_target()
            label("swmlab")
            mov(isr,x)
            push(noblock)
            wait(0,pin,0) [1]
            set(pins, 0)
            wait(1,pin,0) [1]
            set(pins, 1)
            jmp(x_dec, "swmlab")
            wrap()
        
        # PIO program for dynamo input periodicity (i.e. velocity)
        # 14 instructions
        @rp2.asm_pio()
        def pioperiod():
            pull(block) # receive time out value
            mov(y,osr)
            mov(isr,y)
            push(block)
            wrap_target()
            set(x, 0)
            wait(1,pin,0)
            label("waitzero")    # Usual loop cycle count:
            jmp(x_not_y,"notA")  # 1
            jmp("timeout")
            label("notA")
            jmp(pin,"stillone")  # 2
            jmp("waitone")
            label("stillone")
            jmp(x_dec, "decA")   # 3
            label("decA")
            jmp("waitzero")      # 4
            label("waitone")
            jmp(x_not_y,"notB")  # 1
            jmp("timeout")
            label("notB")
            jmp(pin,"finished")  # 2
            jmp(x_dec, "decB")   # 3
            label("decB")
            jmp("waitone")       # 4
            label("timeout")
            set(x,2)
            label("finished")
            mov(isr,x)
            push(noblock)
            wrap()
        
        self.dist_per_pulse = dist_per_pulse
        # okay to simplify?:  self.pioctrsm = rp2.StateMachine(0, self.__pioctr, in_base=button, jmp_pin=button, set_base=machine.Pin(badger2040.LED), freq=2000000)
        self.pioctrsm = rp2.StateMachine(0, pioctr, in_base=button, jmp_pin=button, freq=2000000)
        self.pioctrsm.active(1)
        self.pioperiodsm = rp2.StateMachine(5, pioperiod, in_base=button, jmp_pin=button, freq=4000000)
        self.pioperiodsm.active(1)
        period_timeout = 5000000
        self.pioperiodsm.put(-period_timeout)
        self.dist_ctr = 0
        # remove any stray FIFO entries (needed?)
        _ = self.distance_since_on()
        self.dist_ctr = 0
        _ = self.velocity()


