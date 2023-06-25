import time
import machine
import badger2040

badger = badger2040.Badger2040()
button_c = badger2040.BUTTONS[badger2040.BUTTON_C]
led = machine.Pin(badger2040.LED)
# sparepin = machine.Pin(2, mode=machine.Pin.OUT)
    
count_c = 0
count_c_changed = True

# Button handling function
def button(pin):
    global count_c, count_c_changed
    #time.sleep(0.01)
    #if not pin.value():
    #    return
    if pin == button_c:
        count_c = count_c+1
        count_c_changed = True
        
for b in badger2040.BUTTONS.values():
    b.irq(trigger=machine.Pin.IRQ_RISING, handler=button)

# input change counter
# 12 instructions
@rp2.asm_pio()
def swmctr1():
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
    irq(clear,4)
    irq(4)
    wrap()

# upper 32b of ctr1
# 7 instructions
@rp2.asm_pio()
def swmctr1_upper():
    set(x,0)
    wrap_target()
    label("upperloop")
    mov(isr,x)
    push(noblock)
    irq(block,4)
    jmp(x_dec,"upperloop")
    wrap()


# return the clock period
# 14 instructions
@rp2.asm_pio()
def swmperiod1():
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
    # Add IRQ set?
    label("finished")
    mov(isr,x)
    push(noblock)
    wrap()

def sign_extend(value, bits):
    sign_bit = 1 << (bits - 1)
    return (value & (sign_bit - 1)) - (value & sign_bit)

# Instantiate a state machine with the blink program, at 2000Hz, with set bound to Pin(25) (LED on the Pico board)
print("Debug: LED pin = ",led)
print("Debug: C button pin = ",button_c)

swmctr1sm = rp2.StateMachine(0, swmctr1, in_base=button_c, jmp_pin=button_c, set_base=machine.Pin(badger2040.LED), freq=2000000)
swmctr1sm.active(1)
print(swmctr1sm)
swmctr1uppersm = rp2.StateMachine(1, swmctr1_upper, freq=2000000)
swmctr1uppersm.active(1)
swmperiod = rp2.StateMachine(5, swmperiod1, in_base=button_c, jmp_pin=button_c, freq=4000000)
swmperiod.active(1)
period_timeout = 5000000
swmperiod.put(-period_timeout)
print("Debug: y=",2**32-swmperiod.get())
#swmctr1sm = rp2.StateMachine(0, swmctr2_tstpull, in_base=button_c, jmp_pin=button_c, set_base=led, out_base=sparepin, pull_thresh=1)
#swmctr1sm = rp2.StateMachine(0, swmctr3, in_base=button_c, jmp_pin=sparepin, set_base=sparepin)

#time.sleep(5)
j = 0
# empty the fifo of stray data
while(swmctr1sm.rx_fifo()>0):
    print("Debug: clearing stray data from ctr lower fifo, j =",2**32-j)
    j = swmctr1sm.get()
while(swmctr1uppersm.rx_fifo()>0):
    print("Debug: clearing stray data from ctr upper fifo, j =",2**32-j)
    j = swmctr1uppersm.get()
while(swmperiod.rx_fifo()>0):
    print("Debug: clearing stray data from period counter fifo, j =",2**32-j)
    j = swmperiod.get()

ctr_upper = 0
while(True):
    if(swmctr1uppersm.rx_fifo()>0):
        ctr_upper = -sign_extend(swmctr1uppersm.get(),32)-1
        print("Debug: ctr_upper changed to ", ctr_upper)
    if(swmctr1sm.rx_fifo()>0):
        ctr_lower = -sign_extend(swmctr1sm.get(),32)-1
        print("count =", ctr_upper, ctr_lower)
    if(swmperiod.rx_fifo()>0):
        x = -sign_extend(swmperiod.get(),32)-1
        if(x<0):
            print("Timeout period")
        else:
            print("period =", x/1000.0, "ms")
    #time.sleep(0.1)

swmctr1sm.active(0)
swmperiod.active(0)
print("Finished")


exit(0)

##############################################################################
# Older code...

# Original test that explicitly names the GPIO pin monitored
@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
def swmctr():
    set(x, 0)
    set(isr, 0)
    wrap_target()
    label("swmlab")
    mov(isr,x)
    push(noblock)
    wait(0,gpio,14) [1]
    set(pins, 0)
    wait(1,gpio,14) [1]
    set(pins, 1)
    jmp(x_dec, "swmlab")
    wrap()

# The following version doesn't work:
# It does count but I couldn't figure out how to get it to be triggered by the nonblocking pull()
# It also polls, which may use power
@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
def swmctr2():
    set(x, 0)
    set(y, 0)
    set(isr, 0)
    wrap_target()
    label("start")
  
    #jmp(pin,"count")
    wait(0,pin,0) [1]
    set(pins, 0)
    pull(noblock)
    jmp(not_osre,"sendctr")
    #jmp("sendctr")
    label("sendfinished")
    wait(1,pin,0) [1]
    # do count
    set(pins, 1)
    jmp(x_dec,"start")
    jmp(y_dec,"start")
    jmp("start")
    # send counter
    label("sendctr")
    out(isr,32)
    mov(osr,null)
    mov(isr,x)
    push()
    mov(isr,y)
    push()
    jmp("sendfinished")
    wrap()


@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
def swmctr2_tstpull():
    set(x, 0)
    set(y, 0)
    set(isr, 0)
    wrap_target()
    label("start")
    set(pins, 0)
    pull(block)  # works with blocking pull, otherwise it just pulls from x reg
    jmp(not_osre,"sendctr")
    #jmp("sendctr")
    label("sendfinished")
    # do count
    set(pins, 1)
    jmp(x_dec,"start")
    jmp(y_dec,"start")
    jmp("start")
    # send counter
    label("sendctr")
    out(pins,1)
    mov(osr,null)
    mov(isr,x)
    push()
    mov(isr,y)
    push()
    jmp("sendfinished")
    wrap()
    
    
# The following is a work in progress
# Problem: trying to trigger send by setting an output to 1
@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
def swmctr3():
    set(x, 0)
    set(y, 0)
    set(isr, 0)
    wrap_target()
    label("start")
    wait(0,pin,0) [1]
    #jmp(pin,"sendctr")
    jmp("sendctr")
    label("sendctr_rtn")
    wait(1,pin,0) [1]
    jmp(x_dec,"start")
    jmp(y_dec,"start")
    jmp("start")
    label("sendctr")
    set(pins,0)
    mov(isr,x)
    push(noblock)
    mov(isr,y)
    push(noblock)
    jmp("sendctr_rtn")
    wrap()

