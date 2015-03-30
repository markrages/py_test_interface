#!/usr/bin/python

import serial, time, os

class ChecksumError(Exception): pass
class LengthError(Exception): pass

import re

regexps={re.compile("DC ([- ][0-9.]*) +mV"): ['m','V']}

class Packet:
    def __init__(self):
        self.string=''
        self.unit=''
        self.value=None
        self.mode=None

    def load_data(self,data):

        if len(data) != 14:
            #print "length",len(data)
            raise LengthError

        string=None

        for r in regexps.keys():
            m=r.match(data)
            if m:
                string=m.group(1)
                mult, unit = regexps[r]
                break

        if string is None:
            print data# DC  000.0  mV
            raise ChecksumError
                
        self.unit=mult+unit

        try:
            self.value=float(string) * {'M':1e6,
                                        'K':1e3,
                                        ' ':1,
                                        'm':1e-3,
                                        'u':1e-6,
                                        'n':1e-9,
                                        'p':1e-12}[mult]
                                        
        except ValueError:
            print "got no value for ",string
            self.value=None

        self.string=string

    def __repr__(self):
        return "%s %s"%(self.string,self.unit) #self.value)

class RS22_805Meter:
    def __init__(self, port='/dev/ttyPROLIFIC'):

        if not os.path.lexists(port):
            port = '/dev/ttyS0'

        self.s=serial.Serial(port=port, timeout=0.1,
                             baudrate=600,
                             bytesize=serial.SEVENBITS,
                             parity=serial.PARITY_NONE,
                             stopbits=serial.STOPBITS_TWO)
        self.s.setDTR()
        self.s.setRTS(0)
        self.packet=None

    def flush(self):
        self.s.flushInput()

    def get_packet(self):
        data_accum=''
        for i in range(20):
            self.s.write("D")
            data_accum+=self.s.read(14)            
            if len(data_accum)>=14:
                p=Packet()
                try:
                    p.load_data(data_accum[-14:])
                    return p
                except ChecksumError:
                    pass

import time
if __name__=="__main__":
    meter=RS22_805Meter()
    while 1:
        p=meter.get_packet()
        if p and None != p.value:
            print p.value
        
            
