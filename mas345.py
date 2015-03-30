#!/usr/bin/python

import serial, time, os

modes=['DC V','AC V','DC uA','DC mA','DC A',
       'AC uA','AC mA','AC A','OHM','CAP',
       'Hz','Net Hz','Amp Hz','Duty','Net Duty',
       'Amp Duty','Width','Net Width','Amp Width','Diode',
       'Continuity','hFE','Logic','dBm','EF','Temperature']

segs={ 0x00: ' ',
       0x20: '-',
       0xd7: '0',
       0x50: '1',
       0xb5: '2',
       0xf1: '3',
       0x72: '4',
       0xe3: '5',
       0xe7: '6',
       0x51: '7',
       0xf7: '8',
       0xf3: '9',
       0x87: 'C',
       0xa7: 'E',
       0x27: 'F',
       0x86: 'L',
       0x66: 'h',
       0x64: 'n',
       0x37: 'P',
       0x24: 'r',
       0xa6: 't'}

byte1=['Hz','Ohms','K','M','F','A','V','m']
byte2=['u','n','dBm','S','%','hFE','REL','MIN']
byte7=['Beep','Diode','Bat','Hold','-','~','RS232','Auto']

decimal=0x08

class ChecksumError(Exception): pass
class LengthError(Exception): pass
class TimeoutError(Exception): pass

import sys

infinity=9e99999999 # and beyond!

class Packet:
    def __init__(self):
        self.string=''
        self.unit=''
        self.value=None
        self.mode=None
        self.packet_len=14

    def load_data(self,data):
        debug=False

        # DC -0.000   V
        # 01234567890123
        if debug:
            print data
            print "0123456789"*2

        if len(data) != 14:
            raise LengthError

        self.mode =data[0:2]
        self.sign =data[3]
        self.value=data[4:9]
        self.units=data[9:14].strip()

        
        mult=(self.units.strip()+' ')[0]
        if not mult in "MKmunp": mult=' '

        if debug:
            print "mode",self.mode
            print "sign",self.sign
            print "value",self.value
            print "units",self.units        
            print "mult",mult

        if data[2]!=' ' or data[13] != '\r':
            raise ChecksumError

        
        if 'O' in self.value and 'L' in self.value:
            self.value=infinity
        else:
            self.value=float(self.value) * {'M':1e6,
                                            'K':1e3,
                                            ' ':1,
                                            'm':1e-3,
                                            'u':1e-6,
                                            'n':1e-9,
                                            'p':1e-12}[mult]
                                        

        if self.sign=='-':
            self.value=-self.value

        self.string=data

    def __repr__(self):
        return "%s %s"%(self.string,self.unit) #self.value)

    def __nonzero__(self):
        return None!=self.mode

class MasMeter:
    def __init__(self, port='/dev/ttyPROLIFIC'):

        if not os.path.lexists(port):
            port = '/dev/ttyS0'
      
        self.s=serial.Serial(port=port, timeout=0.1, 
                             baudrate=600, stopbits=2,
                             bytesize=serial.SEVENBITS)
        try:
	    self.s.setDTR()
        except:
            print "Could not set DTR"
	    
	try:
            self.s.setRTS(0)
	except:
	    print "Could not clear RTS"

        self.s.setTimeout(1)
        self.packet_len=14
        self.packet=None

    def flush(self):
        self.s.flushInput()

    def try_for_packet(self):
        """ May return a None packet"""
        self.s.write('\0'*14)

        d=self.s.read(self.packet_len)

        if len(d)==0: raise TimeoutError,"is meter turned on?"

        if len(d)<14: return False

        #if len(d): print "read %d bytes"%len(d)

        p=Packet()
        
        while 1:
            if len(d)>2*self.packet_len: return False
            try:
                p.load_data(d[-self.packet_len:])
                return p
            except ChecksumError:
                d=d+self.s.read(1)
            except LengthError:
                return False
                
        else:
            return False

    def get_packet(self, tries=-1):
        while tries!=0:
            p=self.try_for_packet()
            if p: return p
            tries-=1

    def get_dc_voltage(self):
        return self.get_specific_measurement('DC','V')

    def get_specific_measurement(self, mode, units):
        connected_printed=False
        units_printed=False
        while 1:
            p=self.get_packet(10)
            if p==None:
                if not connected_printed:
                    print "Meter not connected?"
                    connected_printed=True
            elif p.mode!=mode or not units in p.units:
                if not units_printed:
                    print "Please set meter to %s %s"%(mode,units)
                    units_printed=True
            else:
                return p;

import time
if __name__=="__main__":
    meter=MasMeter()
    while 1:
        p=meter.get_dc_voltage()
        if p and None != p.value:
            print p.value
        else:
            print "x"
        sys.stdout.flush()
