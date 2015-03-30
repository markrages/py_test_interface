#!/usr/bin/python

import serial, time

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

class Packet:
    def __init__(self):
        self.string=''
        self.unit=''
        self.value=None
        self.mode=None

    def load_data(self,data):

        self.data=[ord(x) for x in data]

        if len(data) != 9:
            #print "length",len(data)
            raise LengthError

        checksum=0xff&(57+sum(self.data[:8]))

        if checksum != self.data[8]:
            raise ChecksumError

        self.mode=modes[self.data[0]]

        atts=[]

        for bit in range(8):
            if self.data[1] & (1<<bit): atts.append(byte1[7-bit])
            if self.data[2] & (1<<bit): atts.append(byte2[7-bit])
            if self.data[7] & (1<<bit): atts.append(byte7[7-bit])

        mult = [x for x in ['M','K','m','u','n'] if x in atts]
        if len(mult) > 1: raise
        mult=(mult+[' '])[0]
        
        unit = [x for x in ['Hz','Ohms','F','A','V',
                            'dBm','S','%','hFE',
                            'Beep','Diode'] if x in atts]

        if len(unit) > 1: raise
        unit=(unit+[''])[0]            

        self.unit=mult+unit
        self.atts=atts
        
        string=''
        for d in self.data[3:7]:
            string=segs[d & ~decimal]+string
            if (d & decimal):
                string="."+string
        try:
            self.value=float(string) * {'M':1e6,
                                        'K':1e3,
                                        ' ':1,
                                        'm':1e-3,
                                        'u':1e-6,
                                        'n':1e-9,
                                        'p':1e-12}[mult]
                                        
        except ValueError:
            self.value=None

        if '-' in atts:
            string='-'+string
            self.value=-self.value

        self.string=string

    def __repr__(self):
        return "%s %s"%(self.string,self.unit) #self.value)

    def __nonzero__(self):
        return None!=self.mode

class RSMeter:
    def __init__(self, port='/dev/ttyPROLIFIC'):
        self.s=serial.Serial(port=port, timeout=0.1, baudrate=4800)
        self.s.setDTR()
        self.s.setRTS(0)
        self.packet=None

    def flush(self):
        self.s.flushInput()

    def try_for_packet(self):
        """ May return a None packet"""
        d=self.s.read(9)
        
        if len(d)<9: return False

        #if len(d): print "read %d bytes"%len(d)

        p=Packet()
        
        while 1:
            if len(d)>18: return False
            try:
                p.load_data(d[-9:])
                return p
            except ChecksumError:
                d=d+self.s.read(1)
            except LengthError:
                return False
                
        else:
            return False

    def get_packet(self):
        while 1:
            p=self.try_for_packet()
            if p: return p
    def stop_meter_loop(self): pass # for threaded compat
            
import threading        
class RSMeterThreaded(RSMeter):
    def __init__(self,port='/dev/ttyS0'): 
        RSMeter.__init__(self,port)
        self.reading_lock=threading.Lock()
        self.start_meter_loop()
        self.packet=None

    def run_meter_loop(self):
        while self.meter_loop_running:

            for i in range(5):
                p=self.try_for_packet() 
                if p: break
            #print p
            self.reading_lock.acquire()
            self.packet=p
            self.reading_lock.release()

    def stop_meter_loop(self):
        self.meter_loop_running=False
        self.meter_loop.join()

    def start_meter_loop(self):
        self.meter_loop_running=True
        self.meter_loop=threading.Thread(target=self.run_meter_loop)
        self.meter_loop.start()

    def get_packet(self):
        self.reading_lock.acquire()
        p=self.packet
        self.reading_lock.release()
        return p

import time,sys
if __name__=="__main__":
    try:
        meter=RSMeter(sys.argv[1])
    except IndexError:
        meter=RSMeter()
    try:
        while 1:
            p=meter.get_packet()
            if p and None != p.value:
                print p.value
            time.sleep(1)
            

    except KeyboardInterrupt:
        print "interrupt!"
        meter.stop_meter_loop()
