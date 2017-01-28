#!/usr/bin/env python

import signal
import time

from pirc522 import RFID

run = True
rdr = RFID()
util = rdr.util()
util.debug = True

print(rdr.serial.port)


def end_read(signal,frame):
    global run
    print("\nCtrl+C captured, ending read.")
    run = False
    rdr.cleanup()

signal.signal(signal.SIGINT, end_read)

print("Starting")
while run:
    (error, data) = rdr.request()
    if not error:
        print("\nDetected: " + format(data, "02x"))

    (error, uid) = rdr.anticoll()
    if not error:
        print("Card read UID: " + str(uid))

        print("Setting tag")
        util.set_tag(uid)
        print("\nAuthorizing")
        util.auth(rdr.auth_b, [0xFF] * 6)
        print("\nReading")

        for i in range(64):
            util.read_out(i)

        print("\nDeauthorizing")
        util.deauth()

        time.sleep(1)
