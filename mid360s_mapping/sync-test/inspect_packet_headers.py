"""Listen to existing streams for up to 5s; never send commands to the radar."""
import socket,select,time,struct,binascii,json
from pathlib import Path
from datetime import datetime
sockets=[]; result={}
try:
    for port,name in [(56301,'lidar'),(56401,'imu')]:
        sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        if hasattr(socket,'SO_EXCLUSIVEADDRUSE'): sock.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        sock.bind(('192.168.1.50',port)); sockets.append(sock); result[name]=[]
    deadline=time.monotonic()+5
    while time.monotonic()<deadline and any(len(v)<3 for v in result.values()):
        for sock in select.select(sockets,[],[],.2)[0]:
            packet,addr=sock.recvfrom(65535)
            if addr[0]!='192.168.1.119': continue
            name='lidar' if sock.getsockname()[1]==56301 else 'imu'
            if len(result[name])>=3: continue
            if len(packet)<36: result[name].append({'short_header_hex':packet.hex()}); continue
            result[name].append({'source':addr,'bytes':len(packet),'version':packet[0],
                'declared_length':struct.unpack_from('<H',packet,1)[0],
                'dot_num':struct.unpack_from('<H',packet,5)[0],
                'data_type':packet[10],'time_type':packet[11],
                'crc_field':hex(struct.unpack_from('<I',packet,24)[0]),
                'crc_computed':hex(binascii.crc32(packet[28:])),
                'timestamp':struct.unpack_from('<Q',packet,28)[0],
                'header_hex':packet[:36].hex()})
finally:
    for sock in sockets: sock.close()
p=Path(__file__).parent/'sessions'/('headers-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
p.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2)); print(p)
