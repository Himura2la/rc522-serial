#! python3

import time
import threading
import tkinter
from tkinter import ttk
from pirc522 import RFID
import serial.tools.list_ports


class Application(ttk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.pack(fill='both', expand=True)

        self.master.title("RC522 Tool")
        self.master.minsize(200, 80)
        self.master.geometry("500x300")

        self.w_toolbar = ttk.Frame(self)
        self.ports_list = [p.device for p in serial.tools.list_ports.comports()]

        try:
            self.port = tkinter.StringVar(self, list(serial.tools.list_ports.grep("USB"))[-1].device)
        except IndexError:
            self.port = tkinter.StringVar(self, self.ports_list[-1])
        self.w_port = ttk.Combobox(self.w_toolbar, values=self.ports_list, textvariable=self.port, width=15)
        self.w_port.current(self.ports_list.index(self.port.get()))

        self.w_dump = ttk.Button(self.w_toolbar, text="Dump", command=self.dump, width=6,)
        self.w_connect = ttk.Button(self.w_toolbar, text="Connect", command=self.connect, width=10)
        self.input = tkinter.StringVar(self)
        self.w_in = ttk.Entry(self.w_toolbar, width=3, textvariable=self.input)

        self.w_out = tkinter.Text(self, height=1)
        # self.w_progressbar = ttk.Progressbar(self)

        # Layouting

        self.w_port.pack(side='left')
        self.w_connect.pack(side='left')
        self.w_in.pack(side='left', fill='x', expand=True)
        self.w_dump.pack(side='left')

        self.w_toolbar.pack(side='top', fill="x")
        self.w_out.pack(fill='both', expand=True)
        # self.w_progressbar.pack(side="bottom", fill="x")

        self.button_state("disconnected")

        # Declaring

        self.rdr, self.util = None, None

    def connect(self):
        if not self.rdr:
            self.output("Connecting to RC522 via %s..." % self.port.get())
            t = threading.Thread(target=self.connect_sync)
            t.start()
            self.button_state("connecting")
        else:
            self.rdr.serial.close()
            self.rdr.cleanup()
            self.rdr, self.util = None, None
            self.button_state('disconnected')
            self.output("Port %s was closed." % self.port.get())

    def connect_sync(self):
        self.rdr = RFID(self.port.get(), output_func=self.output)
        if self.rdr.connected:
            self.util = self.rdr.util()
            self.util.debug = True
            self.button_state('connected')
            self.output("Ready!")
        else:
            self.rdr = None
            self.button_state('disconnected')

    def button_state(self, state):
        if state == "disconnected":
            self.w_connect['state'] = 'normal'
            self.w_connect['text'] = "Connect"
            self.w_dump['state'] = 'disabled'
        if state == "connecting":
            self.w_connect['text'] = "Waiting..."
            self.w_connect['state'] = 'disabled'
        if state == "connected":
            self.w_dump['state'] = 'normal'
            self.w_connect['state'] = 'normal'
            self.w_connect['text'] = "Disconnect"

    def dump(self):
        try:
            blocks = int(self.input.get())
        except ValueError:
            self.input.set("1")
            blocks = int(self.input.get())
            self.output("Unable to read the number of blocks. Dumping one...")

        t = threading.Thread(target=self.dump_sync, args=(blocks,))
        t.start()

    def output(self, *text, end="\n"):
        self.w_out.insert('end', " ".join(text) + end)
        self.w_out.see('end')

    def dump_sync(self, size):
        self.output("Waiting for a tag...")
        while True:
            time.sleep(0.3)
            success, data = self.rdr.request()
            if success:
                self.output("Detected: {:#04x}".format(data))

                success, uid = self.rdr.anti_collision()
                self.util.set_tag(uid)

                self.output("Authorizing...")
                self.util.auth(self.rdr.auth_b, [0xFF] * 6)

                self.output("Reading...")
                self.util.dump(size)

                self.output("Deauthorizing...")
                self.util.deauth()
                break

root = tkinter.Tk()
app = Application(master=root)
app.output("Started.")
app.mainloop()

if app.rdr:
    app.rdr.cleanup()
