# py_test_interface

Python scripts for controlling electronics test equipment.

These are scripts for connecting to random bits of equipment.  I hope
they save time for somebody.

Each script is standalone and self-contained but require
[pySerial](http://pyserial.sourceforge.net/).  On Ubuntu, "`apt-get
install python-serial`" will solve it.

They have been tested with Ubuntu but they should work on any platform
with pySerial.

[bk1697.py](bk1697.py) controls the BK Precision 1697 DC power supply.
This power supply is made by [Manson](http://www.manson.com.hk/) as
[SDP-2405](http://www.manson.com.hk/products/detail/168).  It appears
under names "PeakTech 1885" or"FULLWatt Premier 5.1" according to
comments at
http://www.eevblog.com/2009/05/10/eevblog-8-part-2-of-2-bk-precision-1697-programmable-lab-power-supply/

[mas345.py](mas345.py) takes readings from the Mastech MAS-345 DMM.
This is a Chinese DMM that is about the cheapest way to get calibrated
voltage / current readings into a computer.  It provides isolation via
infrared diode transmitter / receiver pair.  So the 9V battery only
lasts a few days during data logging use.  These meters are rebranded
and sold by lots of people.  The data interface is a bitmap of the
enabled LCD segments.  The '345 includes a thermocouple, there is also
MAS-343 without temperature measurement.

[rs22_805.py](rs22_805.py) takes readings from the Radio Shack (RIP) 22-805 DMM.

[rsmeter.py](rsmeter.py) takes readings from an older Radio Shack
meter that was lying around the lab.  I haven't seen it around in a
while -- it was in a yellow case and didn't have the Radio Shack part
number on it, if I recall correctly.

[hm305.py](hm305.py) controls the HM305P power supply from Hanmatek (and others).  These supplies are USB controllable, but they just show as an CH341 serial port.  The protocol is described by http://nightflyerfireworks.com/home/fun-with-cheap-programable-power-supplies

hm305.py is Python 3 only. The other scripts are Python 2 only. I no longer have the hardware for them, so I am unwilling to attempt a port that I cannot test.
