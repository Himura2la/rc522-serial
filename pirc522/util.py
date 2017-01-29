
class RFIDUtil(object):
    rfid = None
    method = None
    key = None
    uid = None
    last_auth = None
    debug = False

    def __init__(self, rfid):
        self.rfid = rfid

    """
    Returns block address of spec. block in spec. sector.
    """
    def block_addr(self, sector, block):
        return sector * 4 + block

    """
    Returns sector and it's block representation of block address, e.g.
    S01B03 for sector trailer in second sector.
    """
    def sector_string(self, block_address):
        return "S%dB%d" % ((block_address - (block_address % 4)) / 4, block_address % 4)

    """
    Sets tag for further operations.
    Calls deauth() if card is already set.
    Calls RFID select_tag().
    Returns called select_tag() error state.
    """
    def set_tag(self, uid):
        if self.debug:
            print("Selecting UID " + ":".join(["{:02x}".format(byte) for byte in uid]))

        if self.uid:
            self.deauth()

        self.uid = uid
        return self.rfid.select_tag(uid)

    """
    Sets authentication info for current tag
    """
    def auth(self, auth_method, key):
        self.method = auth_method
        self.key = key

        if self.debug:
            print("Key: " + ":".join(["{:02x}".format(byte) for byte in key]) +
                  ", Method " + ("A" if auth_method == self.rfid.auth_a else "B"))

    """
    Resets authentication info. Calls stop_crypto() if RFID is in auth state
    """
    def deauth(self):
        self.method = None
        self.key = None
        self.last_auth = None

        if self.debug:
            print("Cleaning auth info")

        if self.rfid.authed:
            self.rfid.stop_crypto()
            if self.debug:
                print("Stopping Crypto1")

    def is_tag_set_auth(self):
        return self.uid or self.key or self.method

    """
    Calls RFID card_auth() with saved auth information if needed.
    Returns True in case of success.
    """
    def do_auth(self, block_address, silent=False, force=False):
        auth_data = block_address, self.method, self.key, self.uid
        if (self.last_auth != auth_data) or force:
            if self.debug and not silent:
                print("Auth into" + self.sector_string(block_address))
            self.last_auth = auth_data
            return self.rfid.card_auth(self.method, block_address, self.key, self.uid)
        else:
            if self.debug and not silent:
                print("Already authenticated")
            return True

    """
    Writes sector trailer of specified sector. Tag and auth must be set - does auth.
    If value is None, value of byte is kept.
    Returns error state.
    """
    def write_trailer(self, sector, key_a=(0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF), auth_bits=(0xFF, 0x07, 0x80),
                      user_data=0x69, key_b=(0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF)):
        addr = self.block_addr(sector, 3)
        return self.rewrite(addr, key_a[:6] + auth_bits[:3] + (user_data, ) + key_b[:6])

    """
    Rewrites block with new bytes, keeping the old ones if None is passed. Tag and auth must be set - does auth.
    Returns error state.
    """
    def rewrite(self, block_address, new_bytes):
        if not self.is_tag_set_auth():
            return True

        error = self.do_auth(block_address)
        if not error:
            (error, data) = self.rfid.read(block_address)
            if not error:
                for i in range(len(new_bytes)):
                    if new_bytes[i]:
                        if self.debug:
                            print("Rewrite [{0}]: {:#04x} -> {:#04x}".format(i, data[i], new_bytes[i]))
                        data[i] = new_bytes[i]

                error = self.rfid.write(block_address, data)
                if self.debug:
                    print("Writing " + str(data) + " to " + self.sector_string(block_address))
        return error

    """
    Prints sector/block number and contents of block. Tag and auth must be set - does auth.
    """
    def read(self, block_address, silent=True):
        if not self.is_tag_set_auth():
            return False, None
        if not self.do_auth(block_address, silent=True):
            return False, None
        error, data = self.rfid.read(block_address)
        if not silent:
            if not error:
                print(self.sector_string(block_address) + ": ", end="")
                for chunk in zip(*[iter(data)]*4):
                    print(" ".join(["{:02x}".format(byte) for byte in chunk]), end="  ")
                print()
            else:
                print("Error on " + self.sector_string(block_address))
        return error, data

    def dump(self, sectors=16):
        for i in range(sectors * 4):
            self.read(i, silent=False)
            if i % 4 == 0 and i > 0:
                print()
