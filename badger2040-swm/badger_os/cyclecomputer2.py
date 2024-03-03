# R 2023-11-15
# TODO: remove use of upper distance counter since it will never be needed (would need to cycle over 20k miles between stops!)
# TODO: remove use of .format
import time
import json
import machine
import badger2040
import badger_os
import WIFI_CONFIG
# from network_manager import NetworkManager
# import network
# import ntptime
# import urequests
# import uasyncio
import gc
from movement import Movement
import netbat
import cycledisplay
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

disp=cycledisplay.cycledisplay()

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


# Button handling function
def button(pin):
    time.sleep(0.01)
    if not pin.value():
        return
    if(button_up.value()):
        manifest = ["main.py", "cycle_computer.py", "cyclecomputer2.py", "netbat.py", "movement.py", "cycledisplay.py"]
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
        disp.display_message("REBOOTING")
        machine.reset()
    if(button_up.value()):
        disp.display_message("Getting network time")
        try:
            netbat.get_network_time()
            disp.display_message("SUCCESS!!!")
        except:
            disp.display_message("Failed to get network time")


#def days_in_month(month, year):
#    if month == 2 and ((year % 4 == 0 and year % 100 != 0) or year % 400 == 0):
#        return 29
#    return (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[month - 1]




def read_battery_level():
    global batpc
    batpc = netbat.readBatteryPercent()




for b in badger2040.BUTTONS.values():
    if(b!=button_c):  # don't handle button_c since this is being used for velocity measurement
        b.irq(trigger=machine.Pin.IRQ_RISING, handler=button)

year, month, day, wd, hour, minute, second, _ = rtc.datetime()
last_second = second
last_minute = minute
read_battery_level()


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
        disp.draw_display(velocity=velocity, batpc=batpc, distance=distance, dist_since_on=dist_since_on,
                          year=year, month=month, day=day, hour=hour, minute=minute, second=second)

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
                disp.display_message("Failed to save state")
            # Since we were moving but have now stopped we may be near a wifi hotspot,
            # so try using NTP to set the time
            try:
                netbat.get_network_time()
                disp.display_message("GOT NETWORK TIME!")
            except:
                print("Failed to get network time")

        display.set_update_speed(1)
        disp.draw_display(velocity=velocity, batpc=batpc, distance=distance,
                          year=year, month=month, day=day, hour=hour, minute=minute, second=second, dist_since_on=dist_since_on,
                          sleeping=True)
        print("Debug: Going for a deep sleep")
        if(hour < 7): # sleep a lot at night
            badger2040.sleep_for(60) # sleep for 1 hour
        else:
            badger2040.sleep_for(1) # sleep for 1 minute

    
