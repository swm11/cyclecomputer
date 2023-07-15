import time
import machine
import badger2040
import WIFI_CONFIG
from picographics import PicoGraphics, DISPLAY_INKY_PACK
from network_manager import NetworkManager
import uasyncio
import gc

# SWM: the following doesn't yet work
#def swm_get_time_from_loc(lat=52.228, lon=0.0969):
#    data = f"latitude={lat}&logitude={lon}"
#    print(f"debug: data = {data}")
#    return urlopen("https://timeapi.io/api/Time/current/coordinate", data);

woken_by_button = badger2040.woken_by_button()  # Must be done before we clear_pressed_to_wake

# distance in meters for every pulse from the dynamo
dist_per_pulse=0.15461538
distance = 0
velocity = 0
    

# SWM:
def get_network_time():
    if not(badger2040.is_wireless()):
        return
    import network
    import ntptime
    import WIFI_CONFIG
    print("Debug: SSID=", WIFI_CONFIG.SSID)
    # from urllib.urequest import urlopen

    display.led(128)
    try:
        #display.connect()
        network_manager = NetworkManager(WIFI_CONFIG.COUNTRY) # , status_handler=self.status_handler)
        uasyncio.get_event_loop().run_until_complete(network_manager.client(WIFI_CONFIG.SSID, WIFI_CONFIG.PSK))
        gc.collect()
        net = network.WLAN(network.STA_IF).ifconfig()
        if display.isconnected():
            ntptime.timeout=2
            ntptime.host = "uk.pool.ntp.org"
            ntptime.settime()
            year, month, day, wd, hour, minute, second, _ = rtc.datetime()
            ymd = "{:04}/{:02}/{:02}".format(year, month, day)
            print(f"Finished ntptime, date: {ymd}")
            if(year>2022):
                # NTP has probably set the time correctly, so save it
                badger2040.pico_rtc_to_pcf()
            #print(swm_get_time_from_loc())
        else:
            print("Failed to connect to the network")
    except (RuntimeError, OSError) as e:
        print(f"Wireless Error: {e.value}")
    display.led(0)
    network_manager.disconnect()

def setPad(gpio, value):
    machine.mem32[0x4001c000 | (4+ (4 * gpio))] = value
    
def getPad(gpio):
    return machine.mem32[0x4001c000 | (4+ (4 * gpio))]

def readVsys():
    oldpad = getPad(29)
    setPad(29,128)  #no pulls, no output, no input
    adc_Vsys = machine.ADC(3)
    Vsys = float(adc_Vsys.read_u16()) * 3.0 * 3.3 / float(1 << 16)
    setPad(29,oldpad)
    return Vsys

def batVolt2Percent(voltage):
    empty = 2.99
    full = 3.85
    if(voltage<empty):
        return 0.0
    if(voltage>=full):
        return 100.0
    return (voltage-empty)*100/(full-empty)


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

display = badger2040.Badger2040()
# SWM: rotation by 180deg works but not 90deg :(
display.display = PicoGraphics(display=DISPLAY_INKY_PACK,rotate=90)
# SWM: display.set_thickness(4)
display.set_thickness(3)

WIDTH, HEIGHT = display.get_bounds()
# Thonny overwrites the Pico RTC so re-sync from the physical RTC if we can
try:
    badger2040.pcf_to_pico_rtc()
except RuntimeError:
    pass

rtc = machine.RTC()
get_network_time()
button_c = badger2040.BUTTONS[badger2040.BUTTON_C]
period = "Timeout"
swmctr1sm = rp2.StateMachine(0, swmctr1, in_base=button_c, jmp_pin=button_c, set_base=machine.Pin(badger2040.LED), freq=2000000)
swmctr1sm.active(1)
print(swmctr1sm)
swmctr1uppersm = rp2.StateMachine(1, swmctr1_upper, freq=2000000)
swmctr1uppersm.active(1)
swmperiod = rp2.StateMachine(5, swmperiod1, in_base=button_c, jmp_pin=button_c, freq=4000000)
swmperiod.active(1)
period_timeout = 5000000
swmperiod.put(-period_timeout)

# empty the fifo of stray data
while(swmctr1sm.rx_fifo()>0):
    j = swmctr1sm.get()
while(swmctr1uppersm.rx_fifo()>0):
    j = swmctr1uppersm.get()
while(swmperiod.rx_fifo()>0):
    j = swmperiod.get()


display.set_update_speed(2)


display.set_font("sans")
bat_font_size = 0.5
clk_font_size = 0.5
dat_font_size = 0.5
speed_font_size = 1
dist_font_size = 1
cursors = ["year", "month", "day", "hour", "minute"]
set_clock = False
toggle_set_clock = False
cursor = 0
last = 0
count_c = 0
count_c_changed = False
button_a = badger2040.BUTTONS[badger2040.BUTTON_A]
button_b = badger2040.BUTTONS[badger2040.BUTTON_B]
button_c = badger2040.BUTTONS[badger2040.BUTTON_C]

button_up = badger2040.BUTTONS[badger2040.BUTTON_UP]
button_down = badger2040.BUTTONS[badger2040.BUTTON_DOWN]
time_y = 34

# Button handling function
def button(pin):
#    global count_c, count_c_changed
    time.sleep(0.01)
    if not pin.value():
        return
    if button_a.value() and button_b.value():
        machine.reset()
#    if pin == button_c:
#        count_c = count_c+1
#        count_c_changed = True


def days_in_month(month, year):
    if month == 2 and ((year % 4 == 0 and year % 100 != 0) or year % 400 == 0):
        return 29
    return (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[month - 1]


def draw_display():
    global second_offset, second_unit_offset, time_y, count_c, bat_font_size, clk_font_size, dat_font_size, distance, velocity

    display.led(128)
    batpc = batVolt2Percent(readVsys())
    bat = "{:0.1f}%".format(batpc)
    #cnt = "{:05}".format(count_c)
    dst = f"{distance:.3f}km"
    vel = f"{velocity:.2f}km/h"
    hms = "{:02}:{:02}:{:02}".format(hour, minute, second)
    ymd = "{:04}/{:02}/{:02}".format(year, month, day)

    hms_width = display.measure_text(hms, clk_font_size)
    hms_offset = int((badger2040.WIDTH / 2) - (hms_width / 2))
    h_width = display.measure_text(hms[0:2], clk_font_size)
    mi_width = display.measure_text(hms[3:5], clk_font_size)
    mi_offset = display.measure_text(hms[0:3], clk_font_size)

#    ymd_width = display.measure_text(ymd, dat_font_size)
#    ymd_offset = int((badger2040.WIDTH / 2) - (ymd_width / 2))
#    y_width = display.measure_text(ymd[0:4], dat_font_size)
#    m_width = display.measure_text(ymd[5:7], dat_font_size)
#    m_offset = display.measure_text(ymd[0:5], dat_font_size)
    d_width = display.measure_text(ymd, dat_font_size)
    d_offset = badger2040.WIDTH - d_width

#    bat_width = display.measure_text(bat, bat_font_size)
#    bat_offset = int((badger2040.WIDTH / 2) - (bat_width / 2))

    display.set_pen(15)
    display.clear()
    display.set_pen(0)

    
    display.text(hms, d_offset, 30, wordwrap=0, scale=clk_font_size)
    display.text(ymd, d_offset, 60, wordwrap=0, scale=dat_font_size)
    display.text(bat, d_offset, 90, wordwrap=0, scale=bat_font_size)

    display.text(vel, 0, int(badger2040.HEIGHT/2)-15, wordwrap=0, scale=speed_font_size)
    display.text(dst, 0, badger2040.HEIGHT-15, wordwrap=0, scale=dist_font_size)

    hms = "{:02}:{:02}:".format(hour, minute)
    second_offset = hms_offset + display.measure_text(hms, clk_font_size)
    hms = "{:02}:{:02}:{}".format(hour, minute, second // 10)
    second_unit_offset = hms_offset + display.measure_text(hms, clk_font_size)

    display.set_update_speed(2)
    display.update()
    display.set_update_speed(3)
    display.led(0)


for b in badger2040.BUTTONS.values():
    if(b!=button_c):  # don't handle button_c since this is being used for velocity measurement
        b.irq(trigger=machine.Pin.IRQ_RISING, handler=button)

year, month, day, wd, hour, minute, second, _ = rtc.datetime()


# SWM: why is the following needed?
#if (year, month, day) == (2021, 1, 1):
#    rtc.datetime((2022, 2, 28, 0, 12, 0, 0, 0))

last_second = second
last_minute = minute
draw_display()


ctr_upper = 0
ctr_lower = 0
while True:
    if(swmctr1uppersm.rx_fifo()>0):
        ctr_upper = -sign_extend(swmctr1uppersm.get(),32)-1
    if(swmctr1sm.rx_fifo()>0):
        ctr_lower = -sign_extend(swmctr1sm.get(),32)-1
    new_count_c = ctr_upper<<32 | ctr_lower
    count_c_changed = new_count_c != count_c
    count_c = new_count_c
    distance = count_c * dist_per_pulse / 1000.0
    if(swmperiod.rx_fifo()>0):
        x = -sign_extend(swmperiod.get(),32)-1
        if(x<0):
            velocity = 0.0
        else:
            velocity = dist_per_pulse*x/1000000.0
        #period = f"{(x/1000.0):.2f}ms"
        # convert m/s to km/h
        velocity = velocity * 60*60/1000.0
    
    if not set_clock:
        year, month, day, wd, hour, minute, second, _ = rtc.datetime()
        if((minute != last_minute) or count_c_changed):
            count_c_changed=False
            last_minute = minute
            last_second = second
            draw_display()
#        else:
#            if(second != last_second):
#                draw_second()
#                last_second = second

    if toggle_set_clock:
        set_clock = not set_clock
        print(f"Set clock changed to: {set_clock}")
        toggle_set_clock = False
        draw_display()

    time.sleep(0.01)
