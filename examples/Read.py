#!/usr/bin/env python

import time
from pirc522 import RFID

rdr = RFID()
util = rdr.util()
util.debug = True

print("Used port:", rdr.serial.port)
print("Waiting for tag...")

while True:
    try:
        success, data = rdr.request()
        if success:
            print("\nDetected: {:#04x}".format(data))

        success, uid = rdr.anti_collision()
        if success:
            util.set_tag(uid)
            print("\nAuthorizing...")
            util.auth(rdr.auth_b, [0xFF] * 6)
            print("\nReading...")

            util.dump(1)

            print("\nDeauthorizing...")
            util.deauth()

            time.sleep(3)
            print("\nWaiting for tag...")
    except KeyboardInterrupt:
        break

print("\nCtrl+C captured, ending read.")
rdr.cleanup()
