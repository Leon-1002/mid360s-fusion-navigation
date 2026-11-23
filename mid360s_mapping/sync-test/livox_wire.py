"""Mid360/S official UDP command format; no persistent configuration writes."""
import binascii
import struct
from datetime import datetime, timezone

SYNC_KEYS = (0x8006, 0x8009, 0x800A, 0x800B, 0x800C)

def pack_command(seq, command, payload, command_type=0, sender=0):
    prefix = struct.pack('<BBHIHBB6s', 0xAA, 0, 24+len(payload), seq & 0xffff,
                         command, command_type, sender, b'\0'*6)
    return prefix + struct.pack('<HI', binascii.crc_hqx(prefix, 0xffff),
                                binascii.crc32(payload) if payload else 0) + payload

def unpack_command(data):
    if len(data) < 24:
        raise ValueError('short command packet')
    sof, version, length, seq, command, kind, sender = struct.unpack_from('<BBHIHBB', data)
    crc16, crc32 = struct.unpack_from('<HI', data, 18)
    payload = data[24:]
    if sof != 0xaa or version != 0 or length != len(data):
        raise ValueError('invalid command header/length')
    if crc16 != binascii.crc_hqx(data[:18], 0xffff):
        raise ValueError('header CRC mismatch')
    if crc32 != (binascii.crc32(payload) if payload else 0):
        raise ValueError('payload CRC mismatch')
    return seq, command, kind, sender, payload

def query_payload(keys=SYNC_KEYS):
    return struct.pack('<HH'+'H'*len(keys),len(keys),0,*keys)

def parse_values(payload):
    if len(payload)<3 or payload[0]!=0:
        raise ValueError(f'query failed: {payload.hex()}')
    count=struct.unpack_from('<H',payload,1)[0]
    pos=3; values={}
    for _ in range(count):
        if pos+4>len(payload): raise ValueError('truncated status key')
        key,size=struct.unpack_from('<HH',payload,pos); pos+=4
        if pos+size>len(payload): raise ValueError('truncated status value')
        if key in values: raise ValueError('duplicate status key')
        values[key]=payload[pos:pos+size]
        pos+=size
    if pos!=len(payload): raise ValueError('trailing status bytes')
    return values

def parse_status(payload):
    raw=parse_values(payload); values={}
    definitions={0x8006:('work_state','B'),0x8009:('local_time_ns','Q'),
                 0x800A:('last_sync_ns','Q'),0x800B:('offset_ns','q'),0x800C:('sync_type','B')}
    for key,data in raw.items():
        if key in definitions:
            name,fmt=definitions[key]
            if len(data)!=struct.calcsize('<'+fmt): raise ValueError('wrong status field size')
            values[name]=struct.unpack('<'+fmt,data)[0]
    return values

def stream_config_payload(key,value):
    # Deliberately prohibit arbitrary device configuration, reboot and resets.
    lengths={0x0006:8,0x0007:8,0x001A:1,0x001C:1}
    if key not in lengths or len(value)!=lengths[key]: raise ValueError('configuration key/size not permitted')
    return struct.pack('<HHHH',1,0,key,len(value))+value

def parse_bench_rmc(line):
    text=line.decode('ascii').strip()
    if not text.startswith('$GPRMC,') or text.count('*')!=1:
        raise ValueError('expected GPRMC')
    body,check=text[1:].split('*')
    crc=0
    for ch in body: crc^=ord(ch)
    if len(check)!=2 or int(check,16)!=crc: raise ValueError('RMC checksum mismatch')
    fields=body.split(',')
    if len(fields)!=13 or fields[2]!='V' or fields[12]!='N':
        raise ValueError('expected BENCH firmware RMC, no GNSS position fix')
    # Explicit test-only contract: reject unrelated GNSS receivers and fractional epochs.
    if len(fields[1])!=9 or fields[1][6:]!='.00' or len(fields[9])!=6:
        raise ValueError('unexpected bench time/date format')
    clock=fields[1][:6]; date=fields[9]
    if not (clock+date).isdigit(): raise ValueError('non-numeric time/date')
    dt=datetime(2000+int(date[4:6]),int(date[2:4]),int(date[:2]),
                int(clock[:2]),int(clock[2:4]),int(clock[4:6]),tzinfo=timezone.utc)
    epoch=int(dt.timestamp())
    if not 1795392000<=epoch<1795392000+7*86400:
        raise ValueError('time outside bench firmware test epoch range')
    return epoch

class Cadence:
    """Require two measured 1 s intervals before forwarding; no silent re-lock."""
    def __init__(self):
        self.last_epoch=None; self.last_rx=None; self.intervals=0
    def observe(self,epoch,rx):
        if self.last_epoch is not None:
            if epoch!=self.last_epoch+1: raise ValueError('RMC skipped/repeated/reversed; stop and start a new session')
            if not .75<=rx-self.last_rx<=1.25: raise ValueError('serial cadence abnormal or buffered; forwarding stopped')
            self.intervals+=1
        self.last_epoch=epoch; self.last_rx=rx
        return self.intervals>=2

def decode_data_header(packet):
    if len(packet)<36 or packet[0]!=0 or struct.unpack_from('<H',packet,1)[0]!=len(packet):
        raise ValueError('invalid point/IMU packet length/version')
    if struct.unpack_from('<I',packet,24)[0]!=binascii.crc32(packet[28:]):
        raise ValueError('point/IMU timestamp and data CRC mismatch')
    # Official timestamp is at byte 28, after CRC32 at byte 24.
    return packet[10],packet[11],struct.unpack_from('<Q',packet,28)[0]
