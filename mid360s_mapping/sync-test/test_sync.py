import binascii
import json
import socket
import struct
import threading
import time
import argparse
import unittest
from unittest.mock import patch
from pathlib import Path
from livox_wire import *
from run_sync import Network,DataMonitor,execute

def rmc(body):
    checksum=0
    for ch in body: checksum^=ord(ch)
    return f'${body}*{checksum:02X}\r\n'.encode()

def data_packet(dtype,epoch):
    body=struct.pack('<Q',epoch)+b'\0'*24
    packet=bytearray(28)
    struct.pack_into('<H',packet,1,28+len(body))
    packet[10]=dtype; packet[11]=2
    struct.pack_into('<I',packet,24,binascii.crc32(body))
    return bytes(packet)+body

class SyncTests(unittest.TestCase):
    def test_sdk_golden(self):
        reference=json.loads(Path(__file__).with_name('sdk-golden.json').read_text())
        self.assertEqual(pack_command(7,0x0202,struct.pack('<BQ',2,1795392000*10**9)).hex(),reference['hex'])
    def test_bad_checksums_lengths(self):
        packet=pack_command(7,0x0202,b'\x02'+b'\0'*8)
        for index in (0,2,8,18,20,25):
            bad=bytearray(packet); bad[index]^=1
            with self.assertRaises(ValueError): unpack_command(bad)
        with self.assertRaises(ValueError): unpack_command(packet[:-1])
    def test_rmc(self):
        sentence=rmc('GPRMC,000000.00,V,,,,,,,231126,,,N')
        self.assertEqual(parse_bench_rmc(sentence),1795392000)
        bad=sentence[:-4]+b'00\r\n'
        with self.assertRaises(ValueError): parse_bench_rmc(bad)
        for body in ('GPRMC,000000.00,A,,,,,,,231126,,,A',
                     'GPRMC,250000.00,V,,,,,,,231126,,,N',
                     'GPRMC,000000.00,V,,,,,,,311126,,,N'):
            with self.assertRaises(ValueError): parse_bench_rmc(rmc(body))
    def test_cadence_and_reset(self):
        cadence=Cadence()
        self.assertFalse(cadence.observe(100,10))
        self.assertFalse(cadence.observe(101,11))
        self.assertTrue(cadence.observe(102,12))
        with self.assertRaises(ValueError): cadence.observe(100,13)
        cadence=Cadence(); cadence.observe(100,10)
        with self.assertRaises(ValueError): cadence.observe(101,10.01)
        cadence=Cadence(); cadence.observe(100,10)
        with self.assertRaises(ValueError): cadence.observe(102,11)
    def test_status_bounds(self):
        p=struct.pack('<BHHHB',0,1,0x800C,1,2)
        self.assertEqual(parse_status(p),{'sync_type':2})
        for bad in (p[:-1],p+b'\0',b'\x01\0\0'):
            with self.assertRaises(ValueError): parse_status(bad)
    def test_data_crc(self):
        packet=data_packet(0,1795392000*10**9)
        self.assertEqual(decode_data_header(packet),(0,2,1795392000*10**9))
        bad=bytearray(packet); bad[28]^=1
        with self.assertRaises(ValueError): decode_data_header(bad)
    def test_configuration_allowlist(self):
        self.assertEqual(stream_config_payload(0x001C,b'\x01'),bytes.fromhex('010000001c00010001'))
        for key,value in [(0x0004,b'\0'*12),(0x0026,b'\x01'),(0x001C,b'\0\0')]:
            with self.assertRaises(ValueError): stream_config_payload(key,value)
    def test_full_bench_loop_with_emulated_devices(self):
        """Real localhost UDP + timed fake UART; also checks config rollback."""
        server=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        server.bind(('127.0.0.2',56100)); server.settimeout(.005)
        original={0x0006:socket.inet_aton('127.0.0.3')+struct.pack('<HH',56301,56300),
                  0x0007:socket.inet_aton('127.0.0.3')+struct.pack('<HH',56401,56400),
                  0x001A:b'\x02',0x001C:b'\x00'}
        config=dict(original); stop=threading.Event(); failures=[]
        latest_ns=0; received_at=0.; stamp=0; last_data=0.
        def emulate():
            nonlocal latest_ns,received_at,stamp,last_data
            try:
                while not stop.is_set():
                    try: raw,addr=server.recvfrom(4096)
                    except socket.timeout: raw=None
                    if raw:
                        seq,cmd,_,_,body=unpack_command(raw)
                        if cmd==0x0101:
                            keys=struct.unpack('<'+'H'*((len(body)-4)//2),body[4:])
                            status={0x8006:b'\x01',0x8009:struct.pack('<Q',stamp),0x800A:struct.pack('<Q',latest_ns),
                                    0x800B:struct.pack('<q',0),0x800C:bytes([2 if latest_ns else 0])}
                            values={**config,**status}
                            reply=struct.pack('<BH',0,len(keys))+b''.join(struct.pack('<HH',k,len(values[k]))+values[k] for k in keys)
                        elif cmd==0x0100:
                            _,_,key,n=struct.unpack_from('<HHHH',body)
                            self.assertEqual(n,len(body)-8); config[key]=body[8:]; reply=b'\0\0\0'
                        elif cmd==0x0202:
                            kind,latest_ns=struct.unpack('<BQ',body); self.assertEqual(kind,2)
                            received_at=time.monotonic(); reply=b'\0'
                        else: raise AssertionError('unexpected hardware command '+hex(cmd))
                        server.sendto(pack_command(seq,cmd,reply,1,1),addr)
                    now=time.monotonic()
                    if latest_ns and now-last_data>.01:
                        stamp=max(stamp+1,latest_ns+int((now-received_at)*1e9)); last_data=now
                        for port,kind in [(56301,1),(56401,0)]:
                            server.sendto(data_packet(kind,stamp),('127.0.0.1',port))
            except BaseException as error: failures.append(error)
        class FakeSerial:
            def __init__(self,*args,**kwargs):
                self.port='FAKE'; self.started=time.monotonic(); self.sent=0
            def reset_input_buffer(self): self.sent=int(time.monotonic()-self.started)
            @property
            def in_waiting(self):
                return 60 if int(time.monotonic()-self.started)>self.sent else 0
            def read(self,count):
                self.sent+=1
                return rmc(f'GPRMC,0000{self.sent:02d}.00,V,,,,,,,231126,,,N')
            def close(self): pass
        thread=threading.Thread(target=emulate); thread.start()
        summary={'rmc_count':0,'time_command_acks':0,'matched_status_count':0}
        events=[]
        try:
            with patch('run_sync.serial.Serial',FakeSerial):
                execute(argparse.Namespace(mode='sync',host='127.0.0.1',lidar='127.0.0.2',port='FAKE',seconds=15),
                        lambda event,**data: events.append({'event':event,**data}),summary)
        except BaseException:
            print('Emulator failures:',repr(failures),'Final events:',events[-3:])
            raise
        finally:
            stop.set(); thread.join(timeout=2); server.close()
        if failures: raise failures[0]
        self.assertEqual(summary['result'],'BENCH_SYNC_PASS',summary)
        self.assertEqual(config,original)
        self.assertTrue(any(e['event']=='stream_restore' and e['success'] for e in events))
    def test_real_udp_loopback_ack(self):
        # Local emulator only; no physical radar or hardware state changes.
        server=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        server.bind(('127.0.0.2',56100)); server.settimeout(2)
        failures=[]
        def respond():
            try:
                packet,addr=server.recvfrom(4096)
                seq,cmd,_,_,payload=unpack_command(packet)
                self.assertEqual(cmd,0x0101); self.assertEqual(payload,query_payload())
                server.sendto(pack_command(seq,cmd,struct.pack('<BHHHB',0,1,0x800C,1,2),1,1),addr)
            except BaseException as error: failures.append(error)
        thread=threading.Thread(target=respond); thread.start()
        net=None
        try:
            net=Network('127.0.0.1','127.0.0.2')
            self.assertEqual(net.status(),{'sync_type':2})
        finally:
            if net: net.close()
            thread.join(timeout=3); server.close()
        self.assertFalse(thread.is_alive())
        if failures: raise failures[0]

if __name__=='__main__': unittest.main(verbosity=2)
