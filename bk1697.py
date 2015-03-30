#!/usr/bin/python

import time
import serial

def get_serial():
    return serial.Serial('/dev/ttyPROLIFIC',baudrate=9600)

# no newline, just carriage return
eol = '\r'

class TimeoutException(Exception): pass

class BK1697(object):
    def __init__(self, sp=None):
        self.sp = sp or get_serial()
        self.channel = 0
        
    def readline(self, timeout=1.):
        'I think one second timeout covers all transactions I sniffed'
        old_timeout = self.sp.getTimeout()
        self.sp.setTimeout(timeout)

        line=''
        while 1:
            c = self.sp.read(1)
            if c=='':
                raise TimeoutException("Timeout after "+repr(line))
            if c==eol:
                self.sp.setTimeout(old_timeout)
                return line
            line+=c
        
    def txrx(self, send, arg=''):
        cmd = send+('%02d'%self.channel)+arg+eol
        #print cmd
        self.sp.write(cmd)

        while 1:
            resp = self.readline()
            if resp == 'OK':
                return
            else:
                yield resp

    def cmd(self,c,c2=''):
        return list(self.txrx(c,c2))


    def __getattr__(self, attr):
        if attr.isupper():
            return lambda *args: self.cmd(attr, *args)
        else:
            raise AttributeError('Dunno about '+repr(attr))

    def begin_session(self):
        """Locks the control panel.  This is not required to control the
        supply, but is useful for long-running tests where curious fingers
        might disrupt things.
        
        Consider a try:, finally: with end_session() so the supply
        isn't left in a locked state.
        """
        self.SESS()

    def end_session(self):
        self.ENDS()
        
    def init_serial(self):
        # this sequence observed at power-up.
        # doesn't appear to be necessary for control of the device
        self.GMAX()
        self.GOVP()
        self.SESS()
        self.GETP()
        self.GETM()
        self.GEEP('004')
        self.GPAL()
        self.GETS()
        self.GETD()
        self.GETD()
        self.GETD()

    def set_volts(self, volts):
        self.VOLT('%03d'%int(volts*10.))
        time.sleep(0.001)

    def set_amps(self, amps):
        self.CURR('%03d'%int(amps*100.))
        time.sleep(0.001)

    def get_volts_amps(self):
        resp = self.GETD()[0]
        volts = int(resp[:4])*0.010
        amps = int(resp[4:])*0.0001
        return volts,amps
    
    def get_volts(self): return self.get_volts_amps()[0]
    def get_amps(self): return self.get_volts_amps()[1]

    def output_on(self, on=True):
        self.SOUT('10'[bool(on)])

    def output_off(self):
        return self.output_on(False)
        
if __name__=="__main__":
    bk = BK1697()

    bk.begin_session()
    try:
        bk.output_on()

        for v in range(300):
            bk.set_volts(v/10.)
            print bk.get_volts_amps()

        bk.set_volts(2.7)

        for a in range(1000):
            bk.set_amps(a/1000.)
            print bk.get_amps()    

        bk.output_off()
    finally:
        try:
            bk.end_session()
        except:
            pass
