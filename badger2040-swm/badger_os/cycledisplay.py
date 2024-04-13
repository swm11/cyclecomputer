#-----------------------------------------------------------------------------
# Cycle Display
#-----------------------------------------------------------------------------
# Copyright (c) Simon W. Moore, March 2024


import badger2040
from picographics import PicoGraphics, DISPLAY_INKY_PACK

class cycledisplay:
    def __init__(self,bst):
        self.display = badger2040.Badger2040()
        self.display.display = PicoGraphics(display=DISPLAY_INKY_PACK)
        self.display.set_thickness(2)
        self.WIDTH, self.HEIGHT = self.display.get_bounds()
        self.display.set_update_speed(1)
        self.display.set_font("sans")
        self.bat_font_size = 0.5
        self.clk_font_size = 0.5
        self.dat_font_size = 0.5
        self.speed_font_size = 1
        self.dist_font_size = 1
        self.cursors = ["year", "month", "day", "hour", "minute"]
        self.cursor = 0
        self.last = 0
        self.bst = bst

    def display_message(self, msg="Hello World!"):
        self.display.set_pen(15)
        self.display.clear()
        self.display.set_pen(0)
        self.display.set_font("bitmap8")
        y=0
        for line in msg.split('\n'):
            self.display.text(line,0,y)
            y=y+16
        self.display.update()

    def __draw_speedometer(self, v, dist_since_on):
        vmax = 30
        if(v>vmax):
            v = vmax
        self.display.set_pen(0)
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
        self.display.line(x0-1,y0+1, x1+1,y0+1)
        self.display.line(x0-1,y0+1, x1+1,y1-1)
        self.display.line(x1+1,y0+1, x1+1,y1-1)
        self.display.triangle(x0,y0, xv,y0, xv,yv)
        self.display.set_font("bitmap6")
        for vt in range(0,vmax,5):
            self.display.text(f"{vt}",x0+vt*scalex,y0+6)
        # Display debug output
        self.display.text(f"{v:0.1f}km/h",vmax*scalex+8,y0-10)
        self.display.text(f"{dist_since_on:.3f}km",vmax*scalex+8,y0-24)

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
    
    def draw_display(self, velocity, distance, dist_since_on, batpc, year, month, day, hour, minute, second, sleeping=False):

        dst = "Hello"
        dst = f"{distance:.3f}km"
        #vel = f"{velocity:.2f}km/h"
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
    
        self.display.set_font("bitmap8")
        d_width = self.display.measure_text(ymd)
        d_offset = badger2040.WIDTH - d_width
        y0=badger2040.HEIGHT-16
        self.display.text(hms, d_offset, y0-20) # , wordwrap=0, scale=self.clk_font_size)
        self.display.text(ymd, d_offset, y0) # , wordwrap=0, scale=self.dat_font_size)

        self.display.set_font("sans")
        self.display.text(dst, 0, badger2040.HEIGHT-15, wordwrap=0, scale=self.dist_font_size)
        self.__draw_speedometer(velocity, dist_since_on)

        self.display.update()
        self.display.set_update_speed(2)

