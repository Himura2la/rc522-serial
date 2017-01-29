import serial
import serial.tools.list_ports

__version__ = "1.0.0"


class RFID(object):
    mode_idle = 0x00
    mode_auth = 0x0E
    mode_receive = 0x08
    mode_transmit = 0x04
    mode_transrec = 0x0C
    mode_reset = 0x0F
    mode_crc = 0x03

    auth_a = 0x60
    auth_b = 0x61

    act_read = 0x30
    act_write = 0xA0
    act_increment = 0xC1
    act_decrement = 0xC0
    act_restore = 0xC2
    act_transfer = 0xB0

    act_reqidl = 0x26
    act_reqall = 0x52
    act_anticl = 0x93
    act_select = 0x93
    act_end = 0x50

    reg_tx_control = 0x14
    length = 16

    authed = False

    def __init__(self, dev=None, output_func=print):
        self.output = output_func
        self.connected = False
        if not dev:
            try:
                self.port = list(serial.tools.list_ports.grep("USB"))[0].device
            except IndexError:
                self.port = list(serial.tools.list_ports.comports())[0].device
        else:
            self.port = dev
        self.baud_rate = 9600
        self.serial = serial.Serial(self.port, self.baud_rate)
        self.serial.timeout = 5

        # Initialize
        if not self.reset():
            self.output("MFRC522 does not answer. Closing port.")
            self.serial.close()
            return

        versions = {0x88: 'clone', 0x90: 'v0.0', 0x91: 'v1.0', 0x92: 'v2.0'}
        version = self.dev_read(0x37)
        if version in (0x00, 0xFF):
            self.output("Possible communication problems, trying to continue...")
        elif version in versions.keys():
            self.output("Found MFRC522 " + versions[version] + ". Setting up.")
        else:
            self.output("Found unknown MFRC522, trying to continue...")

        self.dev_write(0x2A, 0x8D)
        self.dev_write(0x2B, 0x3E)
        self.dev_write(0x2D, 30)
        self.dev_write(0x2C, 0)
        self.dev_write(0x15, 0x40)
        self.dev_write(0x11, 0x3D)
        self.switch_antenna(True)
        self.connected = True

    def dev_write(self, address, value):
        command = address & ~(1 << 7)
        self.serial.write(serial.to_bytes([command, value]))
        response = self.serial.read(1)
        if not response:
            self.output("dev_write: Timeout exceeded. Just silence...")
            return False
        if not address == response[0]:
            self.output("W[FAIL] *{0:#04x} -> {1:#010b}: ret={2:#04x}".format(address, value, response[0]))
            return False
        return True

    def dev_read(self, address):
        command = address | (1 << 7)
        self.serial.write(serial.to_bytes([command]))
        return self.serial.read(1)[0]

    def set_bitmask(self, address, mask):
        current = self.dev_read(address)
        self.dev_write(address, current | mask)

    def clear_bitmask(self, address, mask):
        current = self.dev_read(address)
        self.dev_write(address, current & (~mask))

    def switch_antenna(self, state):
        if state:
            current = self.dev_read(self.reg_tx_control)
            if ~(current & 0x03):
                self.set_bitmask(self.reg_tx_control, 0x03)
        else:
            self.clear_bitmask(self.reg_tx_control, 0x03)

    def card_write(self, command, data):
        back_data = []
        back_length = 0
        error = False
        irq = 0x00
        irq_wait = 0x00
        n = 0

        if command == self.mode_auth:
            irq = 0x12
            irq_wait = 0x10
        elif command == self.mode_transrec:
            irq = 0x77
            irq_wait = 0x30

        self.dev_write(0x02, irq | 0x80)
        self.clear_bitmask(0x04, 0x80)
        self.set_bitmask(0x0A, 0x80)
        self.dev_write(0x01, self.mode_idle)

        for i in range(len(data)):
            self.dev_write(0x09, data[i])

        self.dev_write(0x01, command)

        if command == self.mode_transrec:
            self.set_bitmask(0x0D, 0x80)

        while True:
            n = self.dev_read(0x04)
            if n == 0:
                continue  # Too fast
            if n & irq_wait:
                break  # Got it!
            if n & 0x01:
                error = True
                break  # The timer decrements the timer value in register TCounterValReg to zero

        self.clear_bitmask(0x0D, 0x80)

        if not error:
            if (self.dev_read(0x06) & 0x1B) == 0x00:
                error = False

                if n & irq & 0x01:
                    self.output("card_write Error")
                    error = True

                if command == self.mode_transrec:
                    n = self.dev_read(0x0A)
                    last_bits = self.dev_read(0x0C) & 0x07
                    if last_bits != 0:
                        back_length = (n - 1) * 8 + last_bits
                    else:
                        back_length = n * 8

                    if n == 0:
                        n = 1

                    if n > self.length:
                        n = self.length

                    for i in range(n):
                        back_data.append(self.dev_read(0x09))

        return error, back_data, back_length

    """
    Requests for tag.
    Returns False if no tag is present, otherwise returns (True, tag_type)
    """
    def request(self, req_mode=0x26):
        self.dev_write(0x0D, 0x07)
        error, back_data, back_bits = self.card_write(self.mode_transrec, [req_mode, ])
        if error or (back_bits != 0x10):
            return False, back_bits
        return True, back_bits

    """
    Anti-collision detection.
    Returns tuple of (success, tag_ID).
    """
    def anti_collision(self):
        uid_check = 0
        self.dev_write(0x0D, 0x00)

        error, response, back_bits = self.card_write(self.mode_transrec, [self.act_anticl, 0x20])
        if error:
            return False, response
        if len(response) == 5:
            uid = response[:4]
            check_byte = response[4]
            for byte in uid:
                uid_check = uid_check ^ byte
            if uid_check != check_byte:
                return False, response
        else:
            return False, response
        return True, uid

    def calculate_crc(self, data):
        self.clear_bitmask(0x05, 0x04)
        self.set_bitmask(0x0A, 0x80)

        for i in range(len(data)):
            self.dev_write(0x09, data[i])
        self.dev_write(0x01, self.mode_crc)

        i = 255
        while True:
            n = self.dev_read(0x05)
            i -= 1
            if not ((i != 0) and not (n & 0x04)):
                break
        return [self.dev_read(0x22), self.dev_read(0x21)]

    """
    Selects tag for further usage.
    uid -- list or tuple with four bytes tag ID
    Returns True if succeed.
    """
    def select_tag(self, uid):
        buf = [self.act_select, 0x70] + uid
        uid_check = 0
        for byte in uid:
            uid_check = uid_check ^ byte
        buf.append(uid_check)
        buf += self.calculate_crc(buf)

        error, back_data, back_length = self.card_write(self.mode_transrec, buf)

        if (not error) and (back_length == 0x18):
            return True
        else:
            return False

    """
    Authenticates to use specified block address. Tag must be selected using select_tag(uid) before auth.
    auth_mode -- RFID.auth_a or RFID.auth_b
    key -- list or tuple with six bytes key
    uid -- list or tuple with four bytes tag ID
    Returns True in case of success.
    """
    def card_auth(self, auth_mode, block_address, key, uid):
        buf = [auth_mode, block_address] + key + uid
        error, back_data, back_length = self.card_write(self.mode_auth, buf)

        if not (self.dev_read(0x08) & 0x08) != 0:
            error = True
        if not error:
            self.authed = True
        return not error

    """Ends operations with Crypto1 usage."""
    def stop_crypto(self):
        self.clear_bitmask(0x08, 0x08)
        self.authed = False

    """Switch state to HALT"""
    def halt(self):
        self.clear_bitmask(0x08, 0x80)
        self.card_write(self.mode_transrec, [self.act_end, 0])
        self.clear_bitmask(0x08, 0x08)
        self.authed = False

    """
    Reads data from block. You should be authenticated before calling read.
    Returns tuple of (error state, read data).
    """
    def read(self, block_address):
        buf = [self.act_read, block_address]
        buf += self.calculate_crc(buf)
        error, back_data, back_length = self.card_write(self.mode_transrec, buf)

        if len(back_data) != 16:
            error = True

        return error, back_data

    """
    Writes data to block. You should be authenticated before calling write.
    Returns True if succeed.
    """
    def write(self, block_address, data):
        buf = [self.act_write, block_address]
        buf += self.calculate_crc(buf)
        error, back_data, back_length = self.card_write(self.mode_transrec, buf)
        if not (back_length == 4) or not ((back_data[0] & 0x0F) == 0x0A):
            error = True

        if not error:
            buf_w = []
            for i in range(16):
                buf_w.append(data[i])

            buf_w += self.calculate_crc(buf_w)
            error, back_data, back_length = self.card_write(self.mode_transrec, buf_w)
            if not (back_length == 4) or not ((back_data[0] & 0x0F) == 0x0A):
                error = True
        return not error

    def reset(self):
        return self.dev_write(0x01, self.mode_reset)

    """
    Calls stop_crypto() if needed and cleanups GPIO.
    """
    def cleanup(self):
        if self.authed:
            self.stop_crypto()
        self.serial.close()

    """
    Creates and returns RFIDUtil object for this RFID instance.
    If module is not present, returns None.
    """
    def util(self):
        try:
            from .util import RFIDUtil
            return RFIDUtil(self, self.output)
        except ImportError:
            return None
