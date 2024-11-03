import os
import time
from network_manager import NetworkManager
import network
import uasyncio
import gc
import WIFI_CONFIG
from umqtt.simple import MQTTClient

CLIENT_ID = "bicycle"
MQTT_BROKER = "hal.local"

m2h_timer = 0
m2h = None

def sub_cb(topic,msg):
    global m2h
    global m2h_timer
    msg = msg.decode('utf8')
    if(topic == b'bicycle/dir'):
        if(len(msg)<1):
            print('DEBUG: not asked for a sensible directory range so exiting')
            m2h_timer = 0
        else:
            m2h_timer = m2h_timer+1
            f = list(filter(lambda a: a.find(msg)>=0, os.listdir('logs')))
            l = len(f)
            print(f"DEBUG: listed logs containing {msg} contains {l} files")
            m2h.pub('files', str(f))
    if(topic == b'bicycle/download'):
        m2h_timer = m2h_timer+1
        try:
            m2h.pub('filename',msg)
            time.sleep(0.1)
            fp = open('logs/'+msg, 'r')
            m2h.pub('contents', fp.read())
            fp.close()
        except:
            print(f'DEBUG: failed to read file logs/{msg}')

class mqtt_hal():
    def __init__(self):
        self.wifiup = False
        try:
            network_manager = NetworkManager(WIFI_CONFIG.COUNTRY) # , status_handler=self.status_handler)
            uasyncio.get_event_loop().run_until_complete(network_manager.client(WIFI_CONFIG.SSID, WIFI_CONFIG.PSK))
            net = network.WLAN(network.STA_IF).ifconfig()
            j=5
            while(not(network.WLAN(network.STA_IF).isconnected()) and (j>0)):
                print("Debug: waiting for network to come up...")
                time.sleep(1)
                j=j-1
            self.wifiup = network.WLAN(network.STA_IF).isconnected()
            if(self.wifiup):
                self.mqttc = MQTTClient(CLIENT_ID, MQTT_BROKER, keepalive=60)
                self.mqttc.set_callback(sub_cb)
                print("DEBUG: connecting to MQTT")
                self.mqttc.connect()
                print("DEBUG: subscribing to MQTT")
                self.mqttc.subscribe("bicycle/dir")
                self.mqttc.subscribe("bicycle/download")
            else:
                print("DEBUG: wifi didn't come up.")
            self.pub('activity','awake')
        except ImportError:
            print("Failed to connect to WiFi")

    def pub(self, topic: str, msg: str):
        self.mqttc.publish('bicycle/'+topic, msg, retain=False, qos=0)
            
if __name__ == '__main__':
    m2h = mqtt_hal()
    m2h_timer = 30
    while(m2h_timer>0):
        # Non-blocking wait for message
        m2h.mqttc.check_msg()
        time.sleep(1)
        m2h_timer = m2h_timer-1
    m2h.pub('activity','sleeping')
    
