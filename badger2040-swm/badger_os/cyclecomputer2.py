# R 2023-11-15
# TODO: remove use of upper distance counter since it will never be needed (would need to cycle over 20k miles between stops!)
# TODO: remove use of .format
import time
import json
import machine
import badger2040
import badger_os
import WIFI_CONFIG
from picographics import PicoGraphics, DISPLAY_INKY_PACK
from network_manager import NetworkManager
import network
import ntptime
import urequests
import uasyncio
import gc
from movement import Movement
import netbat

woken_by_button = badger2040.woken_by_button()  # Must be done before we clear_pressed_to_wake
woken_by_rtc = badger2040.woken_by_rtc()

# distance in meters for every pulse from the dynamo
dist_per_pulse=0.15461538
distance = 0.0
dist_since_on = 0.0
old_distance_since_on = 0.0
velocity = 0
velocity_counter = 0
batpc = 0    

client=None
wlan=None


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
write_new_state_file = False
try:
    in_file = open(state_file, "r")
    restored_state = json.load(in_file)
    in_file.close()
    distance = restored_state["dist"]
    test_year = restored_state["year"]
    print("Debug: read state file")
    print("Debug: restored_state = ", restored_state)
except:
    write_new_state_file = True
    print("No state file so initialising")
    restored_state = {
        "dist"   : 0.0,
        "year"   : year,
        "month"  : month,
        "day"    : day,
        "hour"   : hour,
        "minute" : minute
        }

if(write_new_state_file):
    try:
        out_file = open(state_file, "w")
        json.dump(restored_state, out_file)
        out_file.close()
        print("Debug: wrote state file")
    except:
        print("Failed to write to ", state_file)

button_a = badger2040.BUTTONS[badger2040.BUTTON_A]
button_b = badger2040.BUTTONS[badger2040.BUTTON_B]
button_c = badger2040.BUTTONS[badger2040.BUTTON_C]
button_up = badger2040.BUTTONS[badger2040.BUTTON_UP]
button_down = badger2040.BUTTONS[badger2040.BUTTON_DOWN]
period = "Timeout"

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
time_y = 34

# Button handling function
def button(pin):
    time.sleep(0.01)
    if not pin.value():
        return
    if(button_down.value()):
        url="https://github.com/swm11/cyclecomputer/raw/main/badger2040-swm/badger_os/cycle_computer.py"
        try:
            display_message("Downloading update: "+url)
            netbat.download_file(url, "cycle_computer.py")
            display_message("SUCCESS!!!")
            machine.reset()
        except:
            display_message("Update FAILED :(")
    if button_a.value() and button_b.value():
        display_message("REBOOTING")
        machine.reset()
    if(button_up.value()):
        display_message("Getting network time")
        try:
            netbat.get_network_time()
            display_message("SUCCESS!!!")
        except:
            display_message("Failed to get network time")


def days_in_month(month, year):
    if month == 2 and ((year % 4 == 0 and year % 100 != 0) or year % 400 == 0):
        return 29
    return (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[month - 1]


def draw_speedometer(v):
    global velocity_counter, dist_since_on
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
    display.text(f"{dist_since_on:.3f}km",vmax*scalex+8,y0-24)


def read_battery_level():
    global batpc
    batpc = netbat.readBatteryPercent()


def draw_battery():
    global batpc
    bat = f"{batpc:0.1f}%"
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
moves = Movement(button=button_c, dist_per_pulse=dist_per_pulse)
#moves = Movement(button_c, dist_per_pulse)
velocity = 0
dist_since_on = 0
if(woken_by_rtc):
    sleep_ctr = 0
else:
    sleep_ctr = 12/rapid_update_rate
while True:
    old_dist_since_on = dist_since_on
    old_velocity = velocity

    #timeout = 4
    #while ((timeout>0) and (swmctr1sm.rx_fifo()>0)):
    #        ctr_lower = -sign_extend(swmctr1sm.get(),32)-1
    #        timeout = timeout-1
    #new_count_c = ctr_lower
    #count_c_changed = new_count_c != count_c
    #count_c = new_count_c
    #distance_since_on = count_c * dist_per_pulse / 1000.0
    #distance = restored_state["dist"] + distance_since_on

    #x=-1
    #j=4  # Four entry FIFO that we want to pull from to get a fresh value
    #while((j>0) and (swmperiod.rx_fifo()>0)):
    #    x = -sign_extend(swmperiod.get(),32)-1
    #    velocity_counter = x
    #    j = j-1
    #if((x<0) or (distance_since_on == old_distance_since_on)):
    #    velocity = 0.0
    #else:
    #    # velocity in m/s
    #    velocity = dist_per_pulse*1000000.0/x
    #    #period = f"{(x/1000.0):.2f}ms"
    #    # convert m/s to km/h
    #    velocity = velocity * 60*60/1000.0

    dist_since_on = moves.distance_since_on()
    distance = restored_state["dist"] + dist_since_on
    velocity = moves.velocity()
    moving = old_dist_since_on != dist_since_on

    year, month, day, wd, hour, minute, second, _ = rtc.datetime()
    if((minute != last_minute) or moving or (velocity!=old_velocity)):
        if(minute != last_minute): # try to only read the battery voltage every minute
            read_battery_level()
        last_minute = minute
        last_second = second
        draw_display()

    if(moving):
        # we're moving...
        if(dist_since_on > 1.0):
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
        if(dist_since_on > 1.0):
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
                    print("Debug: wrote state file")
            except:
                display_message("Failed to save state")
            # Since we were moving but have now stopped we may be near a wifi hotspot,
            # so try using NTP to set the time
            try:
                netbat.get_network_time()
                display_message("GOT NETWORK TIME!")
            except:
                print("Failed to get network time")

        display.set_update_speed(1)
        draw_display(sleeping=True)
        print("Debug: Going for a deep sleep")
        if(hour < 7): # sleep a lot at night
            badger2040.sleep_for(60) # sleep for 1 hour
        else:
            badger2040.sleep_for(1) # sleep for 1 minute

    
