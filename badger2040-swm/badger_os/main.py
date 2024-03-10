import time
import machine
import cyclecomputer2

try:
    cyclecomputer2.cyclecomputer2()
except Exception as e:
    print(e)
    with open("main.log", "w") as fw:
        fw.write(str(e))
#        fw.write(traceback.format_exc())

print("Sleeping 10s before reboot")
time.sleep(10)
machine.reset()
