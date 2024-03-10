#-----------------------------------------------------------------------------
# Network and Battery management
#-----------------------------------------------------------------------------
# Copyright (c) Simon W. Moore, March 2024
#
# Note: accessing the network and reading the battery voltage are
# interlinked on the Pico-W - you can only do one or the other due
# a shared pin.

import time
from network_manager import NetworkManager
import network
import ntptime
import urequests
import uasyncio
import gc
import machine
import WIFI_CONFIG
import badger2040

def get_network_time(rtc):
    if not(badger2040.is_wireless()):
        print("Debug: no wireless so cannot get the network time!")
        return
    print("Debug: SSID=", WIFI_CONFIG.SSID)
    # from urllib.urequest import urlopen

    try:
        gc.collect()
        network_manager = NetworkManager(WIFI_CONFIG.COUNTRY) # , status_handler=self.status_handler)
        uasyncio.get_event_loop().run_until_complete(network_manager.client(WIFI_CONFIG.SSID, WIFI_CONFIG.PSK))
        net = network.WLAN(network.STA_IF).ifconfig()
        j=5
        while(not(network.WLAN(network.STA_IF).isconnected()) and (j>0)):
            print("Debug: waiting for network to come up...")
            time.sleep(1)
            j=j-1
        if network.WLAN(network.STA_IF).isconnected():
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
    gc.collect()


def download_file(url,filename):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_CONFIG.SSID, WIFI_CONFIG.PSK)
    fromweb = urequests.get(url)
    with open(filename, "w") as fw:
        fw.write(fromweb.text)
    gc.collect()

    
def _setPadCtrl(gpio, value):
    machine.mem32[0x4001c000 | (4+ (4 * gpio))] = value
    

def _getPadCtrl(gpio):
    return machine.mem32[0x4001c000 | (4+ (4 * gpio))]


def _readVsys():
    oldpad29 = _getPadCtrl(29)
    oldpad25 = _getPadCtrl(25)
    _setPadCtrl(29,128)  #no pulls, no output, no input
    #_setPadCtrl(25,0)    #output drive 2mA
    adc_en_vsys = machine.Pin(25, machine.Pin.OUT)
    adc_en_vsys.value(1)
    time.sleep_ms(1) # SWM: allow time for pin to stabalise?
    adc_Vsys = machine.ADC(3)
    Vsys = float(adc_Vsys.read_u16()) * 3.0 * 3.3 / float(1 << 16)
    _setPadCtrl(29,oldpad29)
    _setPadCtrl(25,oldpad25)
    return Vsys


def _batVolt2Percent(voltage):
    empty = 2.99
    full = 3.85
    if(voltage<empty):
        return 0.0
    if(voltage>=full):
        return 100.0
    return (voltage-empty)*100/(full-empty)


def readBatteryPercent():
    batv = _readVsys()
    return _batVolt2Percent(batv)
