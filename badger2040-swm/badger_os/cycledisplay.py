#-----------------------------------------------------------------------------
# Cycle Display
#-----------------------------------------------------------------------------
# Copyright (c) Simon W. Moore, March 2024


import badger2040
import math
import time
from picographics import PicoGraphics, DISPLAY_INKY_PACK

class cycledisplay:
    def __init__(self,bst=False):
        self.display = badger2040.Badger2040()
        self.display.display = PicoGraphics(display=DISPLAY_INKY_PACK)
        self.display.set_thickness(2)
        self.WIDTH, self.HEIGHT = self.display.get_bounds()
        self.display.set_update_speed(badger2040.UPDATE_FAST)
        self.display.set_font("bitmap8")
        self.bat_font_size = 0.5
        self.clk_font_size = 0.5
        self.dat_font_size = 0.5
        self.speed_font_size = 1
        self.dist_font_size = 1
        self.cursors = ["year", "month", "day", "hour", "minute"]
        self.cursor = 0
        self.last = 0
        self.bst = bst

    def display_message(self, msg="No message", scale=2):
        self.display.set_update_speed(badger2040.UPDATE_FAST)
        self.display.set_pen(15)
        self.display.clear()
        self.display.set_pen(0)
        self.display.set_font("bitmap8")
        y=0
        for line in msg.split('\n'):
            self.display.text(line,0,y,scale=scale)
            y=y+16
        self.display.update()

    def __draw_speedometer(self, v):
        os = (self.HEIGHT//2)-1
        vmax=40
        sa = math.pi*2/vmax
        self.display.circle(os,os,os)
        self.display.set_pen(15)
        self.display.circle(os,os,40)
        self.display.set_pen(0)
        vi = int(v)
        vs = f"{vi}"
        vw = self.display.measure_text(vs)  # note this is for scale=2 width
        self.display.text(vs, os-vw+2, os-18, scale=4)
        self.display.text("km/h", os-2*8-4, os+14, scale=2)        
        self.display.set_pen(15)
        odx = math.sin(-v*sa)
        ody = math.cos(-v*sa)
        od0 = os-25
        od1 = os-5
        self.display.line(int(od0*odx)+os, int(od0*ody)+os, int(od1*odx)+os, int(od1*ody)+os, 5)
        self.display.set_pen(0)
        
    def __draw_battery(self, batpc):
        bat = f"{batpc:0.1f}%"
        barlen = int(batpc/4)
        h = 12
        w = 30
        x0 = badger2040.WIDTH-w-3
        y0 = 0
        self.display.rectangle(x0,y0,w-3,h)
        self.display.set_pen(15)
        if(barlen<25):
            self.display.rectangle(x0+barlen+1,y0+1,w-5-barlen,h-2)
        self.display.set_pen(0)
        self.display.rectangle(x0+w-3,y0+3,2,h-6)
        self.display.set_font("bitmap6")
        self.display.text(bat, x0-self.display.measure_text(bat)-2, 0)
        self.display.set_font("bitmap8")
    
    def draw_display(self, velocity, distance, dist_since_on, batpc, year, month, day, hour, minute, second, sleeping=False):
        if(self.bst):
            hour = hour+1
            if(hour==24):
                hour = 0
                day = day+1
                # TODO: sort out roll-over of day and month?

        if(sleeping):
            hms = f"{hour:02}:{minute:02}"
        else:
            hms = f"{hour:02}:{minute:02}:{second:02}"
        ymd = f"{year:04}/{month:02}/{day:02}"

        hms_width = self.display.measure_text("12:55:55", self.clk_font_size)
        hms_offset = int((badger2040.WIDTH / 2) - (hms_width / 2))

        self.display.set_pen(15)
        self.display.clear()
        self.display.set_pen(0)
        self.__draw_battery(batpc)
    
        dist_str = f"total: {distance:4.1f}km"
        d_width = self.display.measure_text(dist_str)
        d_offset = self.WIDTH-d_width
        y0=badger2040.HEIGHT-16
        self.display.text(f"trip:  {dist_since_on:2.2f}km", d_offset, y0-60)
        self.display.text(dist_str, d_offset, y0-40)
        self.display.text(hms, d_offset, y0-20)
        self.display.text(ymd, d_offset, y0)

        self.__draw_speedometer(velocity)

        self.display.update()
        self.display.set_update_speed(badger2040.UPDATE_TURBO)


# for debug if running this file directly
if __name__ == "__main__":
    disp = cycledisplay()
    for v in range(30):
        disp.draw_display(velocity=v+0.1, distance=2000.4, dist_since_on=1.34, batpc=91, year=2025, month=6, day=8, hour=21, minute=01, second=4, sleeping=False)
