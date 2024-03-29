# R 2023-11-15
# TODO: remove use of upper distance counter since it will never be needed (would need to cycle over 20k miles between stops!)
# TODO: remove use of .format
import time
import json
import machine
import rp2
import badger2040
import badger_os
import WIFI_CONFIG
from picographics import PicoGraphics, DISPLAY_INKY_PACK
from network_manager import NetworkManager
import network
import urequests
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
#def stopWifi():
#    global client
#    global wlan
#    if not(client==None):
#        client.disconnect()
#        client=None
#    if not(wlan==None):
#        wlan.disconnect()
#        wlan.active(False)
#        wlan.deinit()
#        wlan=None
#    time.sleep_ms(100)

def display_message(msg="Hello World!"):
    global display
    display.set_pen(15)
    display.clear()
    display.set_pen(0)
    display.set_font("bitmap8")
    y=0
    for line in msg.split('\n'):
        display.text(line,0,y)
        y=y+16
    display.update()

def get_network_time():
    if not(badger2040.is_wireless()):
        return
    import ntptime
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
            ymd = f"{year:04}/{month:02}/{day:02}"
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

def download_file(url,filename):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_CONFIG.SSID, WIFI_CONFIG.PSK)
    fromweb = urequests.get(url)
    with open(filename, "w") as fw:
        fw.write(fromweb.text)

def setPadCtrl(gpio, value):
    machine.mem32[0x4001c000 | (4+ (4 * gpio))] = value
    
def getPadCtrl(gpio):
    return machine.mem32[0x4001c000 | (4+ (4 * gpio))]

def readVsys():
    oldpad29 = getPadCtrl(29)
    oldpad25 = getPadCtrl(25)
    setPadCtrl(29,128)  #no pulls, no output, no input
    #setPadCtrl(25,0)    #output drive 2mA
    adc_en_vsys = machine.Pin(25, machine.Pin.OUT)
    adc_en_vsys.value(1)
    time.sleep_ms(1) # SWM: allow time for pin to stabalise?
    adc_Vsys = machine.ADC(3)
    Vsys = float(adc_Vsys.read_u16()) * 3.0 * 3.3 / float(1 << 16)
    setPadCtrl(29,oldpad29)
    setPadCtrl(25,oldpad25)
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
#    irq(clear,4)
#    irq(4)
    wrap()

# upper counter commented out since a 32b counter is sufficient
# upper 32b of ctr1
# 7 instructions
#@rp2.asm_pio()
#def swmctr1_upper():
#    set(x,0)
#    wrap_target()
#    label("upperloop")
#    mov(isr,x)
#    push(noblock)
#    irq(block,4)
#    jmp(x_dec,"upperloop")
#    wrap()


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
    try:
        out_file = open(state_file, "w")
        json.dump(restored_state, out_file)
        out_file.close()
    except:
        print("Failed to write to ", state_file)

button_a = badger2040.BUTTONS[badger2040.BUTTON_A]
button_b = badger2040.BUTTONS[badger2040.BUTTON_B]
button_c = badger2040.BUTTONS[badger2040.BUTTON_C]
button_up = badger2040.BUTTONS[badger2040.BUTTON_UP]
button_down = badger2040.BUTTONS[badger2040.BUTTON_DOWN]
period = "Timeout"
swmctr1sm = rp2.StateMachine(0, swmctr1, in_base=button_c, jmp_pin=button_c, set_base=machine.Pin(badger2040.LED), freq=2000000)
swmctr1sm.active(1)
print(swmctr1sm)
#swmctr1uppersm = rp2.StateMachine(1, swmctr1_upper, freq=2000000)
#swmctr1uppersm.active(1)
swmperiod = rp2.StateMachine(5, swmperiod1, in_base=button_c, jmp_pin=button_c, freq=4000000)
swmperiod.active(1)
period_timeout = 5000000
swmperiod.put(-period_timeout)


# empty the fifo of stray data
timeout=10
while((timeout>0) and (swmctr1sm.rx_fifo()>0)):
    j = swmctr1sm.get()
    timeout = timeout-1
#timeout=10
#while((timeout>0) and (swmctr1uppersm.rx_fifo()>0)):
#    j = swmctr1uppersm.get()
#    timeout = timeout-1
timeout=10
while((timeout>0) and (swmperiod.rx_fifo()>0)):
    j = swmperiod.get()
    timeout = timeout-1


display.set_update_speed(1)


display.set_font("sans")
bat_font_size = 0.5
clk_font_size = 0.5
dat_font_size = 0.5
speed_font_size = 1
dist_font_size = 1
cursors = ["year", "month", "day", "hour", "minute"]
cursor = 0
last = 0
count_c = 0
count_c_changed = False
time_y = 34

# Button handling function
def button(pin):
#    global count_c, count_c_changed
    time.sleep(0.01)
    if not pin.value():
        return
    if(button_up.value()):
        manifest = ["main.py", "manifest.py", "cycle_computer.py", "cyclecomputer2.py", "netbat.py", "movement.py"]
        baseurl="https://github.com/swm11/cyclecomputer/raw/main/badger2040-swm/badger_os/"
        status="Downloading updates:\n"
        try:
            for fn in manifest:
                status=status+fn
                display_message(status)
                print(fn)
                download_file(baseurl+fn, fn)
                status=status+"   SUCCESS!!!\n"
                display_message(status)
            machine.reset()
        except (RuntimeError, OSError) as e:
            print(f"Update FAILED :(\n{e.value}")
            status=status+f"Update FAILED :(\n{e.value}"
            display_message(status)
    if button_a.value() and button_b.value():
        display_message("REBOOTING")
        machine.reset()
    if(button_down.value()):
        display_message("Getting network time")
        try:
            get_network_time()
            display_message("SUCCESS!!!")
        except:
            display_message("Failed to get network time")


def days_in_month(month, year):
    if month == 2 and ((year % 4 == 0 and year % 100 != 0) or year % 400 == 0):
        return 29
    return (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[month - 1]


def draw_speedometer(v):
    global velocity_counter, count_c
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
    # Display debug output
    display.text(f"{v:0.1f}km/h",vmax*scalex+8,y0-10)
    #display.text(f"V={velocity_counter}",vmax*scalex+8,y0-24)
    trip = count_c * dist_per_pulse / 1000
    display.text(f"{trip:.3f}km",vmax*scalex+8,y0-24)


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
    
def draw_display(sleeping=False):
    global second_offset, second_unit_offset, time_y, bat_font_size, clk_font_size, dat_font_size, distance, velocity
    global year, month, day, hour, minute, second

    dst = f"{distance:.3f}km"
    #vel = f"{velocity:.2f}km/h"
    if(sleeping):
        hms = f"{hour:02}:{minute:02}"
    else:
        hms = f"{hour:02}:{minute:02}:{second:02}"
    ymd = f"{year:04}/{month:02}/{day:02}"

    hms_width = display.measure_text("12:55:55", clk_font_size)
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
last_second = second
last_minute = minute
read_battery_level()
#draw_display()


ctr_lower = 0
rapid_update_rate = 3  # max update rate is every 3 seconds
sleep_after = 3*60 # sleep after 3 minutes of not moving
# If we're woken by by the RTC then fast track to sleep, otherwise wait for events (distance)
if(woken_by_rtc):
    sleep_ctr = 0
else:
    sleep_ctr = 12/rapid_update_rate
while True:
    old_distance_since_on = distance_since_on
    old_velocity = velocity
    timeout = 4
    while ((timeout>0) and (swmctr1sm.rx_fifo()>0)):
            ctr_lower = -sign_extend(swmctr1sm.get(),32)-1
            timeout = timeout-1
    new_count_c = ctr_lower
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
    
    year, month, day, wd, hour, minute, second, _ = rtc.datetime()
    if((minute != last_minute) or count_c_changed or (velocity!=old_velocity)):
        if(minute != last_minute): # try to only read the battery voltage every minute
            read_battery_level()
        last_minute = minute
        last_second = second
        draw_display()

    if(count_c_changed):
        # we're moving...
        if(distance_since_on > 1.0):
            # we're really moving...
            sleep_ctr = sleep_after/rapid_update_rate
        else:
            # probably just a nudge
            sleep_ctr = 30/rapid_update_rate
    else:
        # stationary so count down to sleep
        sleep_ctr = sleep_ctr-1

    if(sleep_ctr>0):
        time.sleep(rapid_update_rate)
        #machine.lightsleep(3000) # sleep for 3s
    else:
        # time for a deep sleep
        # determine if we need to save state - have we moved over 1m?
        if(distance_since_on > 1.0):
            save_state = {
                "dist"   : distance,
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
                display_message("Failed to save state")
            # Since we were moving but have now stopped we may be near a wifi hotspot,
            # so try using NTP to set the time
            get_network_time()

        display.set_update_speed(1)
        draw_display(sleeping=True)
        time.sleep(1)
        #badger2040.sleep_for(60) # sleep for 1 hour always to save power
        if((hour < 8) or (batVolt2Percent(batv) < 90)): # sleep a lot at night or if battery is below 90%
            badger2040.sleep_for(60) # sleep for 1 hour
        else:
            badger2040.sleep_for(1) # sleep for 1 minute

    
