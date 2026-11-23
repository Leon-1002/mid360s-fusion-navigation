"""Independent Windows bench test: serial RMC -> official Livox UDP time command.

Never launches mapping, changes host clock or reads rosbag. Streaming destinations,
IMU enable and work target are snapshotted, temporarily set and restored on exit.
"""
import argparse
import json
import socket
import struct
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
import serial
from serial.tools import list_ports
from livox_wire import (pack_command,unpack_command,query_payload,parse_status,
                        parse_bench_rmc,Cadence,decode_data_header,parse_values,stream_config_payload)

class Network:
    def __init__(self,host,lidar):
        self.lidar=lidar; self.seq=0
        self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        try:
            if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
                self.sock.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
            self.sock.bind((host,56101))
            self.sock.settimeout(.22)
        except BaseException:
            self.sock.close(); raise
    def request(self,cmd,payload):
        self.seq=(self.seq+1)&0xffff
        self.sock.sendto(pack_command(self.seq,cmd,payload),(self.lidar,56100))
        deadline=time.monotonic()+.22
        while time.monotonic()<deadline:
            self.sock.settimeout(max(.001,deadline-time.monotonic()))
            raw,addr=self.sock.recvfrom(4096)
            if addr!=(self.lidar,56100): continue
            seq,command,kind,sender,data=unpack_command(raw)
            if (seq,command,kind,sender)==(self.seq,cmd,1,1): return data
        raise TimeoutError('matching radar acknowledgement not received')
    def status(self): return parse_status(self.request(0x0101,query_payload()))
    def read_stream_config(self):
        keys=(0x0006,0x0007,0x001A,0x001C)
        values=parse_values(self.request(0x0101,query_payload(keys)))
        if set(values)!=set(keys): raise ValueError('incomplete stream configuration snapshot')
        for key,value in values.items(): stream_config_payload(key,value)
        if values[0x001A] not in (b'\x01',b'\x02',b'\x09'):
            raise RuntimeError('device working target is not a stable restorable state')
        return values
    def set_stream_value(self,key,value):
        response=self.request(0x0100,stream_config_payload(key,value))
        if len(response)!=3 or response[0]!=0: raise RuntimeError('stream configuration rejected: '+response.hex())
    def close(self): self.sock.close()

def stream_stats():
    return {'packets':0,'gps_packets':0,'regressions':0,'wrong_epoch':0,
            'invalid':0,'crc_verified':0,'crc_unavailable':0,'non_gps':0,
            'last_gps_ns':None,'last_gps_host_monotonic':None,'types':Counter()}

def count_packet(st,packet,kind,epoch,now):
    try: dtype,ttype,stamp,verified=decode_data_header(packet)
    except ValueError: st['invalid']+=1; return
    if (kind=='imu' and dtype!=0) or (kind=='lidar' and dtype not in (1,2,3)):
        st['invalid']+=1; return
    st['packets']+=1; st['types'][ttype]+=1
    st['crc_verified' if verified else 'crc_unavailable']+=1
    if ttype!=2: st['non_gps']+=1
    if ttype==2 and epoch is not None:
        st['gps_packets']+=1
        st['last_gps_host_monotonic']=now
        previous=st['last_gps_ns']
        if previous is not None and stamp<previous: st['regressions']+=1
        if not (epoch-2)*10**9<=stamp<=(epoch+2)*10**9: st['wrong_epoch']+=1
        st['last_gps_ns']=stamp

def timing_data_ok(stats,now):
    return all(s['gps_packets']>=100 and all(s[k]==0 for k in
               ('regressions','wrong_epoch','invalid','non_gps'))
               and s['last_gps_host_monotonic'] is not None
               and now-s['last_gps_host_monotonic']<1 for s in stats.values())

class DataMonitor:
    def __init__(self,host,lidar):
        self.lidar=lidar; self.sockets=[]; self.stats={}; self.steady=None
        try:
            for port,kind in [(56301,'lidar'),(56401,'imu')]:
                sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
                self.sockets.append((sock,kind))
                if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
                    sock.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
                sock.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,4*1024*1024)
                sock.bind((host,port)); sock.setblocking(False)
                self.stats[kind]=stream_stats()
        except BaseException:
            self.close(); raise
    def poll(self,epoch=None):
        for sock,kind in self.sockets:
            for _ in range(5000):
                try: packet,addr=sock.recvfrom(65535)
                except BlockingIOError: break
                if addr[0]!=self.lidar: continue
                now=time.monotonic()
                count_packet(self.stats[kind],packet,kind,epoch,now)
                if self.steady is not None:
                    count_packet(self.steady[kind],packet,kind,epoch,now)
    def close(self):
        for sock,_ in self.sockets: sock.close()

def select_port(requested):
    ports=list(list_ports.comports())
    if requested: return requested
    usb=[p for p in ports if p.vid is not None or 'USB' in p.hwid.upper()]
    if len(usb)!=1:
        raise RuntimeError('Specify -Port COMx. USB serial candidates: '+str([(p.device,p.description) for p in usb]))
    return usb[0].device

def execute(args,emit,summary):
    net=None; monitor=None; ser=None
    original_config=None; changed_keys=[]
    cadence=Cadence(); start=time.monotonic(); buffer=bytearray()
    consecutive_status=0; last_matched_sync=None; last_query=0
    last_epoch=None; last_rmc_rx=None; last_report=0
    steady_start=None; settled_count=0; steady_status_errors=0
    try:
        if args.mode!='serial':
            net=Network(args.host,args.lidar)
            initial=net.status(); emit('initial_status',**initial)
            if args.mode=='sync' and initial.get('work_state') not in (1,2,9):
                raise RuntimeError('Radar not in a normal stable state (work_state='+str(initial.get('work_state'))+'); no time/configuration command sent. Check diagnostics first.')
            if initial.get('sync_type')==1 and args.mode=='sync':
                raise RuntimeError('Radar uses PTP; GPS has lower priority. Stop PTP source before this test.')
            if args.mode=='probe':
                summary['result']='NETWORK_QUERY_PASS'; return
            monitor=DataMonitor(args.host,args.lidar)
        ser=serial.Serial(select_port(args.port),9600,timeout=0,write_timeout=.2,
                          bytesize=8,parity='N',stopbits=1)
        ser.reset_input_buffer()
        if net:
            original_config=net.read_stream_config()
            emit('stream_config_before',values={hex(k):v.hex() for k,v in original_config.items()})
            desired={0x0006:socket.inet_aton(args.host)+struct.pack('<HH',56301,56300),
                     0x0007:socket.inet_aton(args.host)+struct.pack('<HH',56401,56400),
                     0x001C:b'\x01',0x001A:b'\x01'}
            for key,value in desired.items():
                if original_config[key]!=value:
                    # Track before write: the device may apply a request even if its ACK is lost.
                    changed_keys.append(key)
                    net.set_stream_value(key,value)
                    emit('temporary_stream_config',key=hex(key),value=value.hex())
            # Configuration reads/writes may have taken longer than one PPS period.
            ser.reset_input_buffer()
        emit('ready',port=ser.port,mode=args.mode,synthetic_time=True,
             message='Wait for 1 Hz RMC. Do not reset STM32 after synchronization begins.')
        start=time.monotonic()
        while time.monotonic()-start<args.seconds:
            now=time.monotonic()
            if monitor: monitor.poll(last_epoch)
            waiting=ser.in_waiting
            if waiting:
                chunk=ser.read(waiting)
                buffer.extend(chunk)
                if len(buffer)>512: raise ValueError('serial overrun/no valid line framing')
                while b'\n' in buffer:
                    line,_,remaining=buffer.partition(b'\n'); buffer=bytearray(remaining)
                    line=bytes(line)+b'\n'
                    rx=time.monotonic()
                    if line.startswith(b'!ERROR'): raise RuntimeError(line.decode('ascii').strip())
                    if line.startswith(b'!BENCH_ONLY'):
                        if last_epoch is not None: raise RuntimeError('STM32 reset during test')
                        emit('firmware_banner',text=line.decode('ascii').strip()); continue
                    if not line.startswith(b'$GPRMC,'):
                        emit('ignored_serial_line',text=line.decode('ascii',errors='replace').strip()); continue
                    epoch=parse_bench_rmc(line)
                    if buffer or ser.in_waiting:
                        raise ValueError('buffered UART data detected; refuse potentially stale PPS seconds')
                    locked=cadence.observe(epoch,rx)
                    last_epoch=epoch; last_rmc_rx=rx
                    summary['rmc_count']+=1
                    emit('rmc',epoch=epoch,cadence_locked=locked,text=line.decode('ascii').strip())
                    if net and locked:
                        ack=net.request(0x0202,struct.pack('<BQ',2,epoch*10**9))
                        if ack!=b'\0': raise RuntimeError('Radar rejected time command: '+ack.hex())
                        summary['time_command_acks']+=1
                        emit('time_ack',epoch=epoch,host_forward_ack_ms=round((time.monotonic()-rx)*1000,2))
            if last_rmc_rx is not None and time.monotonic()-last_rmc_rx>1.6:
                raise RuntimeError('RMC stream stopped; forwarding halted')
            if last_rmc_rx is None and now-start>8:
                raise RuntimeError('No RMC in 8 seconds; check firmware, PA9->RXD, GND and COM port')
            if net and cadence.intervals>=2 and now-last_query>.8 and last_rmc_rx is not None and .12<now-last_rmc_rx<.55:
                status=net.status(); last_query=time.monotonic()
                matched=(status.get('sync_type')==2 and status.get('last_sync_ns')==last_epoch*10**9)
                if matched and status['last_sync_ns']!=last_matched_sync:
                    consecutive_status+=1; last_matched_sync=status['last_sync_ns']
                elif not matched:
                    consecutive_status=0
                summary['matched_status_count']=consecutive_status
                settled=(matched and status.get('work_state')==1 and
                         last_epoch*10**9<=status.get('local_time_ns',0)<(last_epoch+1)*10**9)
                settled_count=settled_count+1 if settled else 0
                if steady_start is not None and not settled: steady_status_errors+=1
                if steady_start is None and settled_count>=2:
                    # Drain queued transition packets into the retained total counters.
                    monitor.poll(last_epoch)
                    monitor.steady={kind:stream_stats() for kind in monitor.stats}
                    steady_start=time.monotonic()
                    emit('steady_window_started',acquisition_seconds=round(steady_start-start,3),
                         minimum_steady_seconds=10,total_before_steady=monitor.stats)
                emit('radar_status',matched_current_pps=matched,clock_settled=settled,**status)
            if net and steady_start is None and time.monotonic()-start>15:
                raise RuntimeError('Radar clock did not converge within 15 seconds')
            if now-last_report>=5:
                last_report=now
                emit('progress',rmc=summary['rmc_count'],acks=summary['time_command_acks'],matched_status=consecutive_status)
            time.sleep(.005)
        if args.mode=='serial':
            summary['result']='SERIAL_PASS' if cadence.intervals>=10 else 'INCOMPLETE_SERIAL'
        else:
            monitor.poll(last_epoch)
            summary['data']=monitor.stats
            basic=consecutive_status>=10 and summary['time_command_acks']>=10
            duration=0 if steady_start is None else time.monotonic()-steady_start
            summary['steady_seconds']=round(duration,3)
            summary['steady_status_errors']=steady_status_errors
            data_ok=(monitor.steady is not None and duration>=10 and steady_status_errors==0
                     and timing_data_ok(monitor.steady,time.monotonic()))
            summary['result']='STATUS_PASS_DATA_PENDING' if basic else 'INCOMPLETE_SYNC'
            if basic and data_ok:
                unavailable=any(s['crc_unavailable'] for s in monitor.steady.values())
                summary['result']='TIMING_PASS_CRC_UNAVAILABLE' if unavailable else 'BENCH_SYNC_PASS'
                summary['payload_integrity_verified']=not unavailable
    finally:
        if monitor:
            summary['data']=monitor.stats
            summary['steady_data']=monitor.steady
        if ser: ser.close()
        if net:
            try:
                if original_config is not None and changed_keys:
                    restore_errors=[]
                    for key in reversed(changed_keys):
                        try: net.set_stream_value(key,original_config[key])
                        except (OSError,ValueError,RuntimeError) as error:
                            restore_errors.append(f'{hex(key)}: {error}')
                    try:
                        if net.read_stream_config()!=original_config:
                            restore_errors.append('restored configuration readback differs')
                    except (OSError,ValueError,RuntimeError) as error:
                        restore_errors.append('restore readback: '+str(error))
                    summary['restore_errors']=restore_errors
                    emit('stream_restore',success=not restore_errors,errors=restore_errors)
                    if restore_errors:
                        summary['result']='RESTORE_FAILED'
                        raise RuntimeError('Restore failed; see stream_config_before in events.jsonl. Do not resume mapping yet.')
            finally:
                # Keep data ports open until the radar has acknowledged restoration.
                # Closing them earlier can generate ICMP port-unreachable during teardown.
                if monitor: monitor.close()
                net.close()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['serial','probe','sync'],default='serial')
    parser.add_argument('--port')
    parser.add_argument('--host',default='192.168.1.50')
    parser.add_argument('--lidar',default='192.168.1.119')
    parser.add_argument('--seconds',type=int,default=60)
    args=parser.parse_args()
    if args.seconds<15: parser.error('Use at least 15 seconds')
    folder=Path(__file__).parent/'sessions'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    folder.mkdir(parents=True)
    summary={'mode':args.mode,'synthetic_time':True,'real_utc_valid':False,'rmc_count':0,
             'time_command_acks':0,'matched_status_count':0,'result':'NOT_COMPLETED'}
    with (folder/'events.jsonl').open('w',encoding='utf-8') as stream:
        def emit(event,**fields):
            row={'event':event,'host_monotonic':time.monotonic(),**fields}
            text=json.dumps(row,ensure_ascii=False)
            print(text,flush=True); stream.write(text+'\n'); stream.flush()
        emit('session',path=str(folder),mode=args.mode)
        try: execute(args,emit,summary)
        except KeyboardInterrupt:
            summary['result']='INTERRUPTED'; summary['error']='User interrupted'
        except (OSError,ValueError,RuntimeError,serial.SerialException) as error:
            summary['result']='FAILED'; summary['error']=str(error); emit('error',message=str(error))
        finally:
            (folder/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
            emit('summary',**summary)
    print('Report:',folder)
    if summary['result']=='TIMING_PASS_CRC_UNAVAILABLE':
        print('Timing checks passed; point payload CRC is unavailable. Full integrity acceptance remains pending.')
        return 3
    return 0 if summary['result'] in ('SERIAL_PASS','NETWORK_QUERY_PASS','BENCH_SYNC_PASS') else 2

if __name__=='__main__': raise SystemExit(main())
