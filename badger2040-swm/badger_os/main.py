#-----------------------------------------------------------------------------
# Main - launch Cycle Computer 2
#-----------------------------------------------------------------------------
# Copyright (c) Simon W. Moore, March 2024

import sys
import time
import machine
import badger2040
import cyclecomputer2
import cycledisplay

try:
    cyclecomputer2.cyclecomputer2()
except Exception as e:
    print(e)
    with open("main.log", "w") as fw:
        fw.write(str(e))
        sys.print_exception(e, fw)
    errmsg = "Failed to read error log"
    try:
        with open("main.log", "r") as fr:
            errmsg = fr.read()
    except:
        print("ERROR: Failed to read from error log")
    disp=cycledisplay.cycledisplay(bst=False)
    disp.display_message(msg=errmsg, scale=1)
    badger2040.sleep_for(60) # sleep for 1 hour

# if cyclecomputer2 every exits, just sleep ready to be woken up by a button press
badger2040.sleep_for(60) # sleep for 1 hour

## TODO: The following is redundant if on battery power - remove?
#print("Sleeping 10s before reboot")
#time.sleep(10)
#machine.reset()
