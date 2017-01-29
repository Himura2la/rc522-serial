#! python3

import tkinter
from tkinter import ttk
from pirc522 import RFID


class Application(ttk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.pack(fill='both', expand=True)

        self.master.title("MFRC522 Tool")
        self.master.minsize(200, 80)
        self.master.geometry("500x300")

        self.w_toolbar = ttk.Frame(self)

        self.ports_list = ["one", 'two']
        self.port = None
        self.w_port = ttk.Combobox(self.w_toolbar, values=self.ports_list, textvariable=self.port)
        self.w_port.current(0)

        self.w_dump = ttk.Button(self.w_toolbar, text="Dump", command=self.dump)
        self.w_connect = ttk.Button(self.w_toolbar, text="Connect", command=self.connect)
        self.w_in = ttk.Entry(self.w_toolbar)

        self.w_out = tkinter.Text(self, height=1)
        self.w_progressbar = ttk.Progressbar(self)

        # Layouting

        self.w_port.pack(side='left')
        self.w_connect.pack(side='left')
        self.w_in.pack(side='left', fill='x', expand=True)
        self.w_dump.pack(side='left')

        self.w_toolbar.pack(side='top', fill="x")
        self.w_out.pack(fill='both', expand=True)
        self.w_progressbar.pack(side="bottom", fill="x")

    def connect(self):
        print("connect to", self.port)

    def dump(self):
        print("dump", self.port)

root = tkinter.Tk()
app = Application(master=root)
app.mainloop()

exit()




rdr = RFID()
util = rdr.util()
util.debug = True

print("Used port:", rdr.serial.port)
print("Waiting for tag...")

while True:
    try:
        time.sleep(0.3)
        success, data = rdr.request()
        if success:
            print("\nDetected: {:#04x}".format(data))

            success, uid = rdr.anti_collision()
            util.set_tag(uid)

            print("\nAuthorizing...")
            util.auth(rdr.auth_b, [0xFF] * 6)

            print("Writing")
            block = util.block_addr(0, 2)
            util.do_auth(block)
            print(rdr.write(block, [0]*16))

            print("\nReading...")
            util.dump(3)

            print("\nDeauthorizing...")
            util.deauth()

            time.sleep(4)
            print("\nWaiting for tag...")
    except KeyboardInterrupt:
        break

print("\nCtrl+C captured, ending read.")
rdr.cleanup()
