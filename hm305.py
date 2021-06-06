#!/usr/bin/env python3
import struct
import serial
from enum import Enum, unique


class CRCError(Exception):
    pass


def rint(x):
    return int(round(x))


def digit_str(value, max_decimals, disp_digits=4):
    """Fixed-width output of numeric value, to simulate segmented display behavior"""
    int_digits = (
        1 if value < 10 else (2 if value < 100 else 3)
    )  # digits before decimal point
    decimal_avail = min(disp_digits - int_digits, max_decimals)
    return "%*.*f" % (
        disp_digits + 1,
        decimal_avail,
        value,
    )  # +1 total width for decimal point


@unique
class Register(Enum):
    """
    "Documented" registers, manually scraped from included software's settings/*.XML files.

    Some registers seemed to hold constant values that were never observed to change.
    I've commented these as "Always = X?" (with X being unsigned decimal representation).
    The "?" is since it's always unknown if they can still change under some specific conditions that I did not test.
    """

    #
    PowerSwitch = 0x0001  # Power Output 0:OFF, 1:ON
    ProtectStat = 0x0002  #
    Model = 0x0003  # decimal number representation of nominal max volts&amps
    Class = 0x0004  # 2char ASCII string, mostly tells how many digits in display, and whether linear or switching
    Decimals = 0x0005  # For a value of 0x0XYZ, maximum digits after decimal for V=X, I=Y P=Z.  10^X etc used as scaler for reg values.
    Voltage = 0x0010  # Output Voltage actual
    Current = 0x0011  # Output Current actual
    Power_x4 = 0x0012  # Output Power actual
    PowerCal_x4 = 0x0014  # Raw calculation of Voltage*Current values (so its scaled by 10^5, instead of 10^3)
    ProtectVol = 0x0020  # OVP setting
    ProtectCur = 0x0021  # OCP setting
    ProtectPow_x4 = 0x0022  # OPP setting. Writable, but doesn't affect anything?  Is there actually any way to toggle OPP on/off?
    SetVol = 0x0030  # Set Const Voltage
    SetCur = 0x0031  # Set Const Current
    SetTimeSpan = (
        0x0032  # Time Span setting pulled from last selected M preset. List mode only.
    )
    # Counts down, corresponding with displayed seconds (HM310T) when List mode on.  read only.

    # "Shortcut Key" settings placed into their own Enum, see below
    PowerStat = 0x8801  # Always = 10? What does this mean?
    defaultShow = 0x8802  # Always = 0? What does this mean?
    SCP = 0x8803  # Always = 0? Manual claims to have Short Circuit Protection, whatever that means.  Is it even possible to trigger?
    Buzzer = 0x8804  # Buzzer toggle 0: Disable, 1: Enable
    DeviceAddr = 0x9999  # Modbus address, Default = 1

    # The following are listed as 4byte wide registers, but the 2nd word are only ever 0 or 1
    # This makes me think second word is to indicate enable/disable of the limit, although that doesn't explain "IL" being enabled.
    UL = 0xC110  # Always = 10?    Minimum allowable output/set Voltage? (No lower limit actually observed)
    UL_en = 0xC111  # Always = 0?     Assuming this is disabled
    UH = 0xC11E  # Always = 3200?  Maximum allowable set Voltage (it matches with upper limit during knob adjustment)
    UH_en = 0xC11F  # Always = 1?
    IL = 0xC120  # Always = 21?    Minimum allowable output/set Current? (No lower limit actually observed)
    IL_en = 0xC121  # Always = 1?     No lower current limit observed, DESPITE this set to 1, so maybe its not "enable"
    IH = 0xC12E  # Always = 10100? Maximum allowable set Current (it matches with upper limit during knob adjustment)
    IH_en = 0xC12F  # Always = 1?

    SDTime = 0xCCCC  # Always = 0? (IIRC)


@unique
class ShortCutKeySettings(Enum):
    """
    M1-M6 Shortcut Key Registers, all RW
        Factory Default Settings for M1-M6 Shortcut Keys
        Voltage: (1, 3, 5, 7, 9,10) / 10 * (UH =  3200) => (320,960,1600,2240,2880,3200)
        Current: (1, 3, 5, 7, 9,10) / 10 * (UL = 10100) => (1010,3030,5050,7070,9090,10100)
        Seconds: 10,11,12,13,14,15
        Enable:   1, 1, 1, 1, 1, 1  I think?      (I think... I messed with List buttons before checking these registers, so )
    """

    M1_Voltage = 0x1000
    M1_Current = 0x1001
    M1_TimeSpan = 0x1002
    M1_Enable = 0x1003
    M2_Voltage = 0x1010
    M2_Current = 0x1011
    M2_TimeSpan = 0x1012
    M2_Enable = 0x1013
    M3_Voltage = 0x1020
    M3_Current = 0x1021
    M3_TimeSpan = 0x1022
    M3_Enable = 0x1023
    M4_Voltage = 0x1030
    M4_Current = 0x1031
    M4_TimeSpan = 0x1032
    M4_Enable = 0x1033
    M5_Voltage = 0x1040
    M5_Current = 0x1041
    M5_TimeSpan = 0x1042
    M5_Enable = 0x1043
    M6_Voltage = 0x1050
    M6_Current = 0x1051
    M6_TimeSpan = 0x1052
    M6_Enable = 0x1053


@unique
class Undoc(Enum):
    """
    "Mystery" registers, not mentioned in XML files, but have been observed to hold non-zero values.
    Pretty much all values are duplicated elsewhere or do not change.
    Probably the only interesting one is 0xA012 (or 0xA022)
    """

    #
    MYS_0040 = 0x0040  # Duplicate of UH (0xC11E) ?
    MYS_0041 = 0x0041  # Duplicate of IH (0xC12E) ?

    MYS_8888 = 0x8888  # Always = 10?  Duplicate of UL(0xCC10)?

    MYS_A010 = 0xA010  # Duplicate of Voltage(0x0010) ?
    MYS_A011 = 0xA011  # Duplicate of Current(0x0011) ?
    MYS_A012 = 0xA012  # Output status?  2/4/6 seem to correspond to Off/CC/CV.  Couldn't produce any other values.
    MYS_A020 = 0xA020  # Duplicate of SetVoltage 0x0030 ?
    MYS_A021 = 0xA021  # Duplicate of SetCurrent 0x0031
    MYS_A022 = 0xA022  # Duplicate of MYS_A012 ?

    MYS_C210 = 0xC210  # Always = 10? Duplicate of UL(0xC110) ?
    MYS_C211 = 0xC211  # Always = 0?
    MYS_C214 = 0xC214  # Always = 960?  3/10ths of UH (same as original M2 Volts, but does not change when M2 edited)
    MYS_C215 = 0xC215  # Always = 1?
    MYS_C21A = 0xC21A  # Always = 2240? 7/10ths of UH (same as original M4 Volts, but does not change when M4 edited)
    MYS_C21B = 0xC21B  # Always = 1?
    MYS_C21E = 0xC21E  # Always = 3200? Duplicate of UH(0xC11E)? (also same as original M6 Volts)
    MYS_C21F = 0xC21F  # Always = 1?

    MYS_C220 = 0xC220  # Always = 21? Duplicate of IL(0xC120) ?
    MYS_C221 = 0xC221  # Always = 1?
    MYS_C224 = 0xC224  # Always = 3030? 3/10ths of IH (same as original M2 Current, but does not change when M2 edited)
    MYS_C225 = 0xC225  # Always = 1?
    MYS_C22A = 0xC22A  # Always = 7070? 7/10ths of IH (same as original M4 Current, but does not change when M4 edited)
    MYS_C22B = 0xC22B  # Always = 1?
    MYS_C22E = 0xC22E  # Always = 10100? Duplicate of IH(0xC12E)? (also same as original M6 Current)
    MYS_C22F = 0xC22F  # Always = 1?


class HM305:
    def __init__(self, device_address=1, fd=None):
        if fd is None:
            fd = serial.Serial("/dev/ttyUSB0", baudrate=9600, timeout=0.5)
        self.s = fd
        self.da = device_address
        decimals = self.read(Register.Decimals.value)
        self.v_decimals = (decimals >> 8) & 0xF
        self.i_decimals = (decimals >> 4) & 0xF
        self.p_decimals = (decimals >> 0) & 0xF

        self.v_scale = 10 ** (self.v_decimals)
        self.i_scale = 10 ** (self.i_decimals)
        self.p_scale = 10 ** (self.p_decimals)

    def send(self, data):
        d = data + struct.pack("<H", self.calculate_crc(data))
        return self.s.write(d)

    def recv(self, length=None):
        data = b""
        if length is None:
            while 1:
                b = self.s.read(length)
                if len(b) == 0:
                    break
                data += b
        else:
            # if expected length is given, then we don't need to wait for timeout
            while len(data) < length:
                b = self.s.read(length - len(data) + 2)  # +2 bytes for CRC
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

    def receive_packet(self, expected, debug=False):
        # +2 bytes for Device Address(Modbus "Station") and Function Code
        expected = expected + 2
        p = self.recv(expected)
        if debug:
            print(p.hex(" ").upper())
        if p:
            if p[1] >= 0x80:
                if p[2] == 0x08:
                    raise CRCError("TX")
                else:
                    raise Exception("Unknown error " + repr(p))
            elif p[1] == 3:
                assert len(p) == p[2] + 3
                return p[3:]
            elif p[1] == 6:
                assert len(p) == 6
                addr, val = struct.unpack(">HH", p[2:])
                return addr, val
            else:
                raise Exception("Unknown response %d" % p)
        else:
            raise Exception("No Connection?")

    def read(self, addr, count=1, show_progress=False):
        COUNT_LIMIT = 125
        data = b""
        recvd = 0
        while recvd < count:
            msg_count = min(COUNT_LIMIT, count - recvd)
            pack = struct.pack(">BBHH", self.da, 3, addr + recvd, msg_count)
            self.send(pack)
            # 1 byte for data length field, 2 bytes per register
            newdata = self.receive_packet(1 + 2 * msg_count)
            assert len(newdata) == 2 * msg_count
            data = data + newdata
            recvd = recvd + msg_count
            if show_progress:
                pct = 100 * recvd / count
                print("\r%6.2f%%" % pct, end="", flush=True)
        if show_progress:
            print("")
        if len(data) == 2:
            (ret,) = struct.unpack(">H", data)
            return ret
        else:
            return data

    def write(self, addr, val, debug=False):
        pack = struct.pack(">BBHH", self.da, 6, addr, val)
        self.send(pack)
        ret = self.receive_packet(4, debug=debug)
        assert addr, val == ret

    def multi_write(self, addr, count, data):
        count = len(barray) / 2
        integers = struct.unpack("H" * count, barray)
        # TODO finish and test this, pretty sure Function Code 16 is supported.
        # pack = struct.pack(">BBHH", self.da, 16, addr, val)
        # self.send(pack)
        # ret = self.receive_packet(4)
        # assert addr, val == ret
        pass

    def read4(self, addr):
        ret = self.read(addr, 2)
        (val,) = struct.unpack(">I", ret)
        return val

    def write4(self, addr, val):
        self.write(addr, val >> 16)
        self.write(addr + 1, val & 0xFFFF)

    @property
    def v(self):
        return self.read(0x10) / self.v_scale

    @v.setter
    def v(self, val):
        self.vset = val

    @property
    def vset(self):
        return self.read(0x30) / self.v_scale

    @vset.setter
    def vset(self, v):
        return self.write(0x30, val=rint(v * self.v_scale))

    @property
    def i(self):
        return self.read(0x11) / self.i_scale

    @i.setter
    def i(self, val):
        self.iset = val

    @property
    def iset(self):
        return self.read(0x31) / self.i_scale

    @iset.setter
    def iset(self, i):
        return self.write(0x31, val=rint(i * self.i_scale))

    @property
    def p(self):
        return self.read4(0x12) / self.p_scale

    def off(self):
        self.write(0x01, 0)

    def on(self):
        self.write(0x01, 1)

    @property
    def beep(self):
        return self.read(0x8804)

    @beep.setter
    def beep(self, v):
        self.write(0x8804, v)

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
        return self.read(0x03)

    @property
    def hw_class(self):
        c = self.read(0x04)
        return chr((c >> 8) & 0xFF) + chr((c >> 0) & 0xFF)

    def scan_all_registers(self, linesize=0x10, hex=True, show_zeros=False):
        REG_COUNT = 0x10000
        print("Searching for treasure...")
        data = self.read(0, REG_COUNT, True)
        print("Offset", end="")
        fmtst = " --%02X" if hex else "  --%02X"
        for i in range(0, linesize):
            print(fmtst % i, end="")
        print("")

        for offset in range(0, REG_COUNT, linesize):
            show = show_zeros
            line = data[offset * 2 : (offset + linesize) * 2]
            if not show:
                for b in line:
                    if b != 0:
                        show = True
                        break
            if show:
                if hex:
                    print("@%04X: %s" % (offset, line.hex(" ", 2).upper()))
                else:
                    regs = len(line) // 2
                    values = struct.unpack(">" + ("H" * regs), line)
                    print(("@%04X:" + "%6s" * regs) % ((offset,) + values))

    def read_documented_registers(self):
        print("All Known Registers (raw decimal values):")
        for reg in Register:
            if reg.name.endswith("_x4"):
                register = self.read4(reg.value)
                print("(0x%04X) %-11s = %u" % (reg.value, reg.name[:-3], register))
            else:
                register = self.read(reg.value)
                print("(0x%04X) %-11s = %u" % (reg.value, reg.name, register))

    def read_shortcutkey_settings(self):
        print("Shortcut Keys (M1-M6) Settings:")
        for reg in ShortCutKeySettings:
            register = self.read(reg.value)
            print("(0x%04X) %s = %u" % (reg.value, reg.name, register))

    def read_undoc_registers(self):
        print("Undocumented Registers (raw decimal values):")
        for reg in Undoc:
            register = self.read(reg.value)
            print("(0x%04X) %s = %u" % (reg.value, reg.name, register))


if __name__ == "__main__":
    hm = HM305()
    # hm.beep = 0
    # hm.vset = 12.34
    print("Model(0x03):", hm.hw_model, " Class(0x04):", repr(hm.hw_class))

    print("")
    hm.read_documented_registers()
    print("")
    hm.read_shortcutkey_settings()
    print("")
    hm.read_undoc_registers()

    # Uncomment below to get dump of all registers. Takes about 3 minutes on 9600 baud.
    # print("")
    # hm.scan_all_registers(linesize=0x10, hex=False, show_zeros=False)

    print("")
    print("Monitoring Output (Ctrl-C to exit):")
    while True:
        # TODO Could get roughly 3x sample rate if these were grouped into a single request/response
        # and unpack from that, but I don't feel like it right now.
        v, i, p = (
            digit_str(hm.v, hm.v_decimals),
            digit_str(hm.i, hm.i_decimals),
            digit_str(hm.p, hm.p_decimals),
        )
        print("\r%s V   %s A   %s W" % (v, i, p), end="")
