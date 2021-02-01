#!/usr/bin/env python3
import struct
import serial


class CRCError(Exception):
    pass


def rint(x):
    return int(round(x))


class HM305:
    def __init__(self, fd=None):
        if fd is None:

            fd = serial.Serial("/dev/ttyCH340", baudrate=9600, timeout=0.1)
        self.s = fd

    def send(self, data):
        d = data + struct.pack("<H", self.calculate_crc(data))
        return self.s.write(d)

    def recv(self, length=1):
        data = b""
        while 1:
            b = self.s.read(length)
            if len(b) == 0:
                break
            data += b

        if len(data) > 2:
            crc = self.calculate_crc(data[:-2])
            (packet_crc,) = struct.unpack("<H", data[-2:])
            if crc != packet_crc:
                raise CRCError("RX")

            return data[:-2]
        return None

    def send_packet(self, device_address=1, address=5, value=None):

        if value is None:
            read = True
            value = 1
        else:
            read = False

        pack = struct.pack(">BBHH", device_address, (6, 3)[read], address, value)
        self.send(pack)

    def receive_packet(self):
        p = self.recv()
        if p:
            if p[1] == 0x83:
                if p[2] == 0x08:
                    raise CRCError("TX")
                else:
                    raise Exception("Unknown error " + repr(p))
            elif p[1] == 3:
                length = p[2]
                assert len(p[3:]) == length
                if length == 2:
                    (ret,) = struct.unpack(">H", p[3:])
                    return ret
                else:
                    return p
            elif p[1] == 6:
                assert len(p[2:]) == 4
                addr, val = struct.unpack(">HH", p[2:])
                return addr, val
            else:
                raise Exception("Unknown response %d" % p)

    def x(self, addr, val=None):
        self.send_packet(address=addr, value=val)
        ret = self.receive_packet()
        if val is None:
            return ret
        else:
            assert addr, val == ret

    def x4(self, addr, val=None):
        if val is None:
            return (self.x(addr) << 16) + self.x(addr + 1)
        else:
            self.x(addr, val >> 16)
            self.x(addr + 1, val & 0xFFFF)

    @property
    def v(self):
        return self.x(0x10) / 100

    @v.setter
    def v(self, val):
        self.vset = val

    @property
    def vset(self):
        return self.x(0x30) / 100

    @vset.setter
    def vset(self, v):
        return self.x(0x30, val=rint(v * 100))

    @property
    def i(self):
        return self.x(0x11) / 1000

    @i.setter
    def i(self, val):
        self.iset = val

    @property
    def iset(self):
        return self.x(0x31) / 1000

    @iset.setter
    def iset(self, i):
        return self.x(0x31, val=rint(i * 1000))

    @property
    def w(self):
        return self.x4(0x12) / 1000

    def off(self):
        self.x(1, 0)

    def on(self):
        self.x(1, 1)

    @property
    def beep(self):
        return self.x(0x8804)

    @beep.setter
    def beep(self, v):
        self.x(0x8804, v)

    @staticmethod
    def calculate_crc(data):
        """Calculate the CRC16 of a datagram"""
        crc = 0xFFFF
        for i in data:
            crc ^= i
            for _ in range(8):
                if crc & 1:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc

    @property
    def hw_model(self):
        return self.x(0x03)

    @property
    def hw_class(self):
        return hex(self.x(0x04))


if __name__ == "__main__":
    hm = HM305()
    hm.beep = 0
    print("Model (0x03):", hm.hw_model)
    print("Class (0x04):", hm.hw_class)
    print(hm.v, "Volts")
    print(hm.i, "Amps")
    print(hm.w, "Watts")
