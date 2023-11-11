import time
import json
import machine
import rp2
import badger2040
import badger_os
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
woken_by_rtc = badger2040.woken_by_rtc()

# distance in meters for every pulse from the dynamo
dist_per_pulse=0.15461538
distance = 0.0
distance_since_on = 0.0
old_distance_since_on = 0.0
velocity = 0
velocity_counter = 0
batv = 0    

client=None
wlan=None

# Bad version of stopWifi that fails to save power?
def stopWifi():
    global client
    global wlan
    if not(client==None):
        client.disconnect()
        client=None
    if not(wlan==None):
        wlan.disconnect()
        wlan.active(False)
        wlan.deinit()
        wlan=None
    time.sleep_ms(100)


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
    network_manager.disconnect()
    display.led(0)


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
display.display = PicoGraphics(display=DISPLAY_INKY_PACK)
# SWM: display.set_thickness(4)
display.set_thickness(2)

WIDTH, HEIGHT = display.get_bounds()
# Thonny overwrites the Pico RTC so re-sync from the physical RTC if we can
try:
    badger2040.pcf_to_pico_rtc()
except RuntimeError:
    pass

rtc = machine.RTC()
if(not(woken_by_rtc)):
    get_network_time()
else:
    j=0 # TODO restore milage from a file?

year, month, day, wd, hour, minute, second, _ = rtc.datetime()
state_file_archive = "logs/{:04}{:02}{:02}state.json".format(year, month, day)
state_file = "state.json"
try:
    in_file = open(state_file, "r")
    restored_state = json.load(in_file)
    in_file.close()
    distance = restored_state["dist"]
    test_year = restored_state["year"]
except:
    print("No state file so initialising")
    restored_state = {
        "dist"   : 0.0,
        "year"   : year,
        "month"  : month,
        "day"    : day,
        "hour"   : hour,
        "minute" : minute
        }
    out_file = open(state_file, "w")
    json.dump(restored_state, out_file)
    out_file.close()
    #except:
    #    print("Failed to write to ", state_file)

distance = restored_state["dist"]

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


display.set_update_speed(1)


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


def draw_speedometer(v):
    global velocity_counter
    vmax = 30
    if(v>vmax):
        v = vmax
    display.set_pen(0)
    scalex=6
    scaley=2
    w=vmax*scalex
    h=vmax*scaley
    x0=1
    y0=h+1+12
    x1=x0+w
    y1=y0-h
    xv=int(x0+v*scalex)
    yv=int(y0-v*scaley)
    display.line(x0-1,y0+1, x1+1,y0+1)
    display.line(x0-1,y0+1, x1+1,y1-1)
    display.line(x1+1,y0+1, x1+1,y1-1)
    display.triangle(x0,y0, xv,y0, xv,yv)
    display.set_font("bitmap6")
    for vt in range(0,vmax,5):
        display.text(f"{vt}",x0+vt*scalex,y0+6)
    #display.set_font("sans")
    display.text(f"{v:0.1f}km/h",vmax*scalex+8,y0-10)
    display.text(f"{velocity_counter}",vmax*scalex+8,y0-24)


def read_battery_level():
    global batv
    batv = readVsys()
#    batv = badger_os.get_battery_level()
#    batpc = batVolt2Percent(batv)
#    bat = f"{batpc:0.1f}%"
#    print(f"Debug: badger OS: bat = {bat}   voltage = {batv:0.2f}")


def draw_battery():
    global batv
    batpc = batVolt2Percent(batv)
    bat = f"{batpc:0.1f}%"
    #print(f"Debug: SWM readVsys: bat = {bat}   voltage = {batv:0.2f}")
    barlen = int(batpc/4)
    h = 12
    w = 30
    x0 = badger2040.WIDTH-w-3
    y0 = 0
    display.rectangle(x0,y0,w-3,h)
    display.set_pen(15)
    if(barlen<25):
        display.rectangle(x0+barlen+1,y0+1,w-5-barlen,h-2)
    display.set_pen(0)
    display.rectangle(x0+w-3,y0+3,2,h-6)
    display.set_font("bitmap6")
    display.text(bat, x0-display.measure_text(bat)-2, 0)
    
def draw_display():
    global second_offset, second_unit_offset, time_y, count_c, bat_font_size, clk_font_size, dat_font_size, distance, velocity

    #cnt = "{:05}".format(count_c)
    dst = f"{distance:.3f}km"
    #vel = f"{velocity:.2f}km/h"
    hms = "{:02}:{:02}:{:02}".format(hour, minute, second)
    ymd = "{:04}/{:02}/{:02}".format(year, month, day)

    hms_width = display.measure_text(hms, clk_font_size)
    hms_offset = int((badger2040.WIDTH / 2) - (hms_width / 2))

    display.set_pen(15)
    display.clear()
    display.set_pen(0)
    draw_battery()
    
    display.set_font("bitmap8")
    d_width = display.measure_text(ymd)
    d_offset = badger2040.WIDTH - d_width
    y0=badger2040.HEIGHT-16
    display.text(hms, d_offset, y0-20) # , wordwrap=0, scale=clk_font_size)
    display.text(ymd, d_offset, y0) # , wordwrap=0, scale=dat_font_size)

    display.set_font("sans")
    display.text(dst, 0, badger2040.HEIGHT-15, wordwrap=0, scale=dist_font_size)
    #display.text(vel, 0, int(badger2040.HEIGHT/2)-15, wordwrap=0, scale=speed_font_size)
    draw_speedometer(velocity)
    #vr = int((badger2040.HEIGHT-16)/2)
    #x0 = vr
    #y0 = x0
    #display.circle(x0,y0,vr)
    #display.set_pen(15)
    #display.circle(x0,y0,vr-2)
    #display.set_pen(0)

    display.update()
    display.set_update_speed(2)


for b in badger2040.BUTTONS.values():
    if(b!=button_c):  # don't handle button_c since this is being used for velocity measurement
        b.irq(trigger=machine.Pin.IRQ_RISING, handler=button)

year, month, day, wd, hour, minute, second, _ = rtc.datetime()


# SWM: why is the following needed?
#if (year, month, day) == (2021, 1, 1):
#    rtc.datetime((2022, 2, 28, 0, 12, 0, 0, 0))

last_second = second
last_minute = minute
read_battery_level()
draw_display()


ctr_upper = 0
ctr_lower = 0
sleep_ctr = 0
while True:
    old_distance_since_on = distance_since_on
    old_velocity = velocity
    for j in range(4):
        if(swmctr1uppersm.rx_fifo()>0):
            ctr_upper = -sign_extend(swmctr1uppersm.get(),32)-1
        if(swmctr1sm.rx_fifo()>0):
            ctr_lower = -sign_extend(swmctr1sm.get(),32)-1
    new_count_c = ctr_upper<<32 | ctr_lower
    count_c_changed = new_count_c != count_c
    count_c = new_count_c
    distance_since_on = count_c * dist_per_pulse / 1000.0
    distance = restored_state["dist"] + distance_since_on

    x=-1
    j=4  # Four entry FIFO that we want to pull from to get a fresh value
    while((j>0) and (swmperiod.rx_fifo()>0)):
        x = -sign_extend(swmperiod.get(),32)-1
        velocity_counter = x
        j = j-1
    if((x<0) or (distance_since_on == old_distance_since_on)):
        velocity = 0.0
    else:
        # velocity in m/s
        velocity = dist_per_pulse*1000000.0/x
        #period = f"{(x/1000.0):.2f}ms"
        # convert m/s to km/h
        velocity = velocity * 60*60/1000.0
    
    if not set_clock:
        year, month, day, wd, hour, minute, second, _ = rtc.datetime()
        if((minute != last_minute) or count_c_changed or (velocity!=old_velocity)):
            if(minute != last_minute): # try to only read the battery voltage every minute
                read_battery_level()
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

    if(count_c_changed):
        sleep_ctr = 0
    else:
        sleep_ctr = sleep_ctr+1

    if(sleep_ctr<10):
        machine.lightsleep(3000) # sleep for 3s
    else:
        if(distance_since_on > 0.0):
            save_state = {
                "dist"   : restored_state["dist"] + distance,
                "year"   : year,
                "month"  : month,
                "day"    : day,
                "hour"   : hour,
                "minute" : minute
            }
            try:
                for fn in [state_file, state_file_archive]:
                    out_file = open(fn, "w")
                    json.dump(save_state, out_file)
                    out_file.close()
            except:
                print("Failed to save state")
        if(hour < 7): # sleep a lot at night
            badger2040.sleep_for(60) # sleep for 1 hour
        else:
            badger2040.sleep_for(1) # sleep for 1 minute

        #badger2040.turn_off()
        
        #if(hour < 7): # Sleep a lot at night
        #    time.sleep(600)
        #else:
        #    time.sleep(20)
    #machine.lightsleep(3000) # sleep for 3,000ms
    
