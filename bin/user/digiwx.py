#!/usr/bin/env python
# Copyright 2024 Matthew Wall, all rights reserved
"""
Collect data from DigiWX hardware.

DigiWX emits data over the serial port, every 5 seconds.  Here are samples:

DW,-007,-014,057,020,006,999,017,29.98,+99999,+03700,004,000,001,000,000,44,04.22,N,068,49.10,W,ME55 ,VINALHAVEN,122.7000,00,U,000,330,110,+020,+007,10,NA,NA,000000,159,01024,00,0,99999,99999,99999,0,CLR,999,CLR,999,CLR,999,CLR,999,71

DW,-004,-013,053,290,000,999,999,30.07,+99999,+04200,004,000,001,000,000,44,04.22,N,068,49.10,W,ME55 ,VINALHAVEN,122.7000,00,U,000,999,999,+024,+009,10,NA,NA,000000,159,01024,00,0,99999,99999,99999,0,CLR,999,CLR,999,CLR,999,CLR,999,77

shot1
DW,-004,-012,054,300,003,999,999,30.07,+99999,+04000,004,000,001,000,000,44,04.22,N,068,49.10,W,ME55 ,VINALHAVEN,122.7000,00,U,000,999,999,+024,+010,10,NA,NA,000000,159,01024,00,0,99999,99999,99999,0,CLR,999,CLR,999,CLR,999,CLR,999,70

shot2
DW,-004,-012,054,290,003,999,999,30.07,+99999,+04000,004,000,001,000,000,44,04.22,N,068,49.10,W,ME55 ,VINALHAVEN,122.7000,00,U,000,999,999,+024,+010,10,NA,NA,000000,159,01024,00,0,99999,99999,99999,0,CLR,999,CLR,999,CLR,999,CLR,999,78

shot3
DW,-004,-012,054,290,003,999,999,30.07,+99999,+04000,004,000,001,000,000,44,04.22,N,068,49.10,W,ME55 ,VINALHAVEN,122.7000,00,U,000,999,999,+024,+010,10,NA,NA,000000,159,01024,00,0,99999,99999,99999,0,CLR,999,CLR,999,CLR,999,CLR,999,78

DW,-004,-012,054,290,003,999,999,30.07,+99999,+04000,004,000,001,000,000,44,04.22,N,068,49.10,W,ME55 ,VINALHAVEN,122.7000,00,U,000,999,999,+024,+010,10,NA,NA,000000,159,01024,00,0,99999,99999,99999,0,CLR,999,CLR,999,CLR,999,CLR,999,78

These are the fields:

 0 DW
 1 -004            temperature (C)
 2 -013            dewpoint (C)
 3 053             relative humdity (%)
 4 290             wind direction (degree)
 5 000             wind speed (knot)
 6 999
 7 999
 8 30.07           pressure inHg
 9 +99999
10 +04200          condensation altitude (feet)
11 004
12 000
13 001
14 000
15 000
16 44              latitude (deg)
17 04.22           latitude (decimal)
18 N               latitude (direction)
19 068             longitude (deg)
20 49.10           longitude (decimal)
21 W               longitude (direction)
22 ME55            airport code (metar?)
23 VINALHAVEN      airport description
24 122.7000
25 00
26 U
27 000
28 999
29 999
30 +024            indicated runway?
31 +009
32 10              visibility?
33 NA
34 NA
35 000000
36 159
37 01024
38 00
39 0
40 99999
41 99999
42 99999
43 0
44 CLR             ceiling
45 999
46 CLR
47 999
48 CLR
49 999
50 CLR
51 999
52 77

"""

from __future__ import with_statement, print_function
import serial
import syslog
import time

import weewx.drivers
from weewx.wxformulas import calculate_rain

DRIVER_NAME = 'DigiWX'
DRIVER_VERSION = '0.1'


def loader(config_dict, _):
    return DigiWXDriver(**config_dict[DRIVER_NAME])


def confeditor_loader():
    return DigiWXConfigurationEditor()


try:
    # WeeWX4 logging
    import logging
    log = logging.getLogger(__name__)
    def logdbg(msg):
        log.debug(msg)
    def loginf(msg):
        log.info(msg)
    def logerr(msg):
        log.error(msg)
except ImportError:
    # WeeWX legacy (v3) logging via syslog
    import syslog
    def logmsg(level, msg):
        syslog.syslog(level, 'digiwx: %s' % msg)
    def logdbg(msg):
        logmsg(syslog.LOG_DEBUG, msg)
    def loginf(msg):
        logmsg(syslog.LOG_INFO, msg)
    def logerr(msg):
        logmsg(syslog.LOG_ERR, msg)


class DigiWXConfigurationEditor(weewx.drivers.AbstractConfEditor):
    @property
    def default_stanza(self):
        return """
[DigiWX]
    # This section is for the DigiWX driver.

    # The serial port to which the station is connected
    port = /dev/ttyS0

    # The driver to use
    driver = user.digiwx
"""

    def prompt_for_settings(self):
        print("Specify the serial port on which the station is connected, for")
        print("example /dev/ttyS0")
        port = self._prompt('port', '/dev/ttyS0')
        return {'port': port}


class DigiWXDriver(weewx.drivers.AbstractDevice):
    def __init__(self, **stn_dict):
        loginf('driver version is %s' % DRIVER_VERSION)
        self._model = stn_dict.get('model', 'WRL')
        port = stn_dict.get('port', DigiWXStation.DEFAULT_PORT)
        self.last_rain = None
        self._station = DigiWXStation(port)
        self._station.open()

    def closePort(self):
        self._station.close()

    @property
    def hardware_name(self):
        return 'DigiWX'

    def genLoopPackets(self):
        while True:
            raw = self._station.get_current()
            if raw:
                logdbg("raw data: %s" % raw)
                data = DigiWXStation.parse_current(raw)
                logdbg("parsed data: %s" % data)
                packet = self._data_to_packet(data)
                yield packet

    def _data_to_packet(self, data):
        pkt = {
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.US,
            'windDir': data.get('wind_dir'),
            'windSpeed': data.get('wind_speed'),
            'inTemp': data.get('temperature_in'),
            'outTemp': data.get('temperature_out'),
            'outHumidity': data.get('humidity'),
            'pressure': data.get('pressure'),
            'rain': calculate_rain(data['rain_total'], self.last_rain)
        }
        self.last_rain = data['rain_total']
        return pkt


class DigiWXStation(object):
    DEFAULT_PORT = '/dev/ttyS0'

    def __init__(self, port):
        self.port = port
        self.baudrate = 19200
        self.timeout = 3 # seconds
        self.max_tries = max_tries
        self.retry_wait = retry_wait
        self.serial_port = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, _, value, traceback):
        self.close()

    def open(self):
        logdbg("open serial port %s" % self.port)
        self.serial_port = serial.Serial(
            self.port, self.baudrate, timeout=self.timeout)

    def close(self):
        if self.serial_port is not None:
            logdbg("close serial port %s" % self.port)
            self.serial_port.close()
            self.serial_port = None

    def get_data(self):
        buf = self.serial_port.readline()
        logdbg("station said: %s" % ' '.join(["%0.2X" % ord(c) for c in buf]))
        buf = buf.strip()
        return buf

    def get_data_with_retry(self):
        for ntries in range(0, self.max_tries):
            try:
                buf = self.get_data()
                return buf
            except (serial.serialutil.SerialException, weewx.WeeWxIOError) as e:
                loginf("Failed attempt %d of %d to get readings: %s"
                       % (ntries + 1, self.max_tries, e))
                time.sleep(self.retry_wait)
        else:
            msg = "Max retries (%d) exceeded for command '%s'" \
                  % (self._max_tries, cmd)
            logerr(msg)
            raise weewx.RetriesExceeded(msg)

    def get_current(self):
        return self.get_data_with_retry()

    @staticmethod
    def parse_current(s):
        # sample responses:
        # DW,-004,-013,053,290,000,999,999,30.07,+99999,+04200,004,000,001,000,
        # 000,44,04.22,N,068,49.10,W,ME55 ,VINALHAVEN,122.7000,00,U,000,999,
        # 999,+024,+009,10,NA,NA,000000,159,01024,00,0,99999,99999,99999,0,CLR,
        # 999,CLR,999,CLR,999,CLR,999,77
        parts = s.split(',')
        data = {
            'temperature': DigiWXStation.parse_int(parts[1]), # C
            'dewpoint': DigiWXStation.parse_int(parts[21]), # C
            'humidity': DigiWXStation.parse_int(parts[3]), # %
            'wind_dir': DigiWXStation.parse_int(parts[4]), # degree
            'wind_speed': DigiWXStation.parse_int(parts[5]), # knot
            'pressure': DigiWXStation.parse_float(parts[8]), # inHg
        }
        return data

    @staticmethod
    def parse_int(s):
        try:
            return int(s)
        except ValueError:
            pass
        return None

    @staticmethod
    def parse_float(s):
        try:
            return float(s)
        except ValueError:
            pass
        return None


# define a main entry point for basic testing of the station without weewx
# engine and service overhead.
#
# PYTHONPATH=bin python digiwx.py

if __name__ == '__main__':
    import optparse

    usage = """%prog [options] [--debug] [--help]"""

    syslog.openlog('wee_digiwx', syslog.LOG_PID | syslog.LOG_CONS)
    syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_INFO))
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--version', dest='version', action='store_true',
                      help='display driver version')
    parser.add_option('--debug', dest='debug', action='store_true',
                      help='display diagnostic information while running')
    parser.add_option('--port', dest='port', metavar='PORT',
                      help='serial port to which the station is connected',
                      default=DigiWXStation.DEFAULT_PORT)

    (options, args) = parser.parse_args()

    if options.version:
        print("digiwx driver version %s" % DRIVER_VERSION)
        exit(1)

    if options.debug:
        syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))

    with DigiWXStation(options.port) as s:
        while True:
            raw = s.get_current()
            print("raw:", raw)
            print("parsed:", DigiWXStation.parse_current(raw))
            time.sleep(5)
