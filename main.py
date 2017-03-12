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

        self.w_connect = ttk.Button(self.w_toolbar, text="Connect", command=self.connect, width=10)
        self.w_dump = ttk.Button(self.w_toolbar, text="Dump", command=self.dump, width=6)
        self.w_read = ttk.Button(self.w_toolbar, text="Read", command=self.read, width=6)
        self.w_write = ttk.Button(self.w_toolbar, text="Write", command=self.write, width=7)
        self.input = tkinter.StringVar(self)
        self.w_in = ttk.Entry(self.w_toolbar, width=3, textvariable=self.input)

        self.w_out = tkinter.Text(self, height=1, state="disabled")
        # self.w_progressbar = ttk.Progressbar(self)

        # Layouting

        self.w_port.pack(side='left')
        self.w_connect.pack(side='left')
        self.w_in.pack(side='left', fill='x', expand=True)
        self.w_write.pack(side='right')
        self.w_read.pack(side='right')
        self.w_dump.pack(side='right')

        self.w_toolbar.pack(side='top', fill="x")
        self.w_out.pack(fill='both', expand=True)
        # self.w_progressbar.pack(side="bottom", fill="x")

        self.toolbar_state("disconnected")

        # Declaring

        self.rdr, self.util = None, None
        self.pending_abort = False

    def output(self, *text, end="\n"):
        self.w_out['state'] = "normal"
        self.w_out.insert('end', " ".join(text) + end)
        self.w_out.see('end')
        self.w_out['state'] = "disabled"

    def connect(self):
        if self.w_connect['text'] == "Abort":
            self.pending_abort = True
            self.output("Stopping the engine...")
            return
        if not self.rdr:
            self.output("Connecting to RC522 via %s..." % self.port.get())
            t = threading.Thread(target=self.connect_sync)
            t.start()
            self.toolbar_state("connecting")
        else:
            app.rdr.cleanup()
            self.rdr, self.util = None, None
            self.toolbar_state('disconnected')
            self.output("Port %s was closed." % self.port.get())

    def connect_sync(self):
        self.rdr = RFID(self.port.get(), output_func=self.output)
        if self.rdr.connected:
            self.util = self.rdr.util()
            self.util.debug = True
            self.toolbar_state('connected')
            self.output("Ready!")
        else:
            self.rdr = None
            self.toolbar_state('disconnected')

    def toolbar_state(self, state):
        if state == "disconnected":
            self.w_port['state'] = 'normal'
            self.w_connect['state'] = 'normal'
            self.w_connect['text'] = "Connect"
            self.w_in['state'] = 'disabled'
            self.w_dump['state'] = 'disabled'
            self.w_read['state'] = 'disabled'
            self.w_write['state'] = 'disabled'
        elif state == "connecting":
            self.w_connect['text'] = "Waiting..."
            self.w_connect['state'] = 'disabled'
        elif state == "connected":
            self.w_port['state'] = 'disabled'
            self.w_connect['state'] = 'normal'
            self.w_connect['text'] = "Disconnect"
            self.w_in['state'] = 'normal'
            self.w_dump['state'] = 'normal'
            self.w_read['state'] = 'normal'
            self.w_write['state'] = 'normal'

    def dump(self):
        try:
            sectors = int(self.input.get())
        except ValueError:
            self.input.set("1")
            sectors = int(self.input.get())
            self.output("Unable to read the number of sectors. Dumping one...")

        threading.Thread(target=self.tag_sync, args=(self.util.dump, (sectors,))).start()

    def tag_sync(self, func, args):
        self.output("Waiting for a tag...")
        self.w_connect['text'] = "Abort"
        while True:
            if self.pending_abort:
                self.output("Aborted!")
                self.pending_abort = False
                break
            time.sleep(0.3)
            success, data = self.rdr.request()
            if success:
                self.output("Detected: {:#04x}".format(data))

                success, uid = self.rdr.anti_collision()
                self.util.set_tag(uid)

                self.output("Authorizing...")
                self.util.auth(self.rdr.auth_b, [0xFF] * 6)

                self.output("Reading...")
                func(*args)

                self.output("Deauthorizing...")
                self.util.deauth()
                break
        self.output("Ready!")
        self.w_connect['text'] = "Disconnect"

    def read(self):
        user_input = self.w_in.get().upper()
        sector = user_input.split("S")
        block = None
        try:
            sector = sector[1]
            sector = int(sector)
        except ValueError:  # block is specified
            try:
                sector, block = sector.split("B")
                sector = int(sector)
                block = int(block)
            except ValueError:
                self.output("Examples: 'S1B1', 'S1'")
                return
        except IndexError:
            if type(sector) is not int:
                self.output("Examples: 'S1B1', 'S1'")
                return
        if block is None:
            threading.Thread(target=self.tag_sync, args=(self.util.dump, (1, sector))).start()
        else:
            threading.Thread(target=self.tag_sync, args=(self.util.read,
                                                         (self.util.block_addr(sector, block), False))).start()

    def write(self):
        pass

root = tkinter.Tk()
app = Application(master=root)
app.output("Started.")
app.mainloop()

if app.rdr:
    app.rdr.cleanup()
