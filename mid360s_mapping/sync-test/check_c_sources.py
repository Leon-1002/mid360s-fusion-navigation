"""Run in WSL. Compile actual firmware RMC generator and SDK2 packet reference."""
import ctypes
import json
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime,timezone
here=Path(__file__).resolve().parent
firmware=here.parent/'stm32/lidar-pps-uart'
sdk=Path('/home/leon/mid360s_lio/sdk')
with tempfile.TemporaryDirectory(prefix='pps-validate-') as temporary:
    temp=Path(temporary)
    subprocess.run(['gcc','-Wall','-Wextra','-Werror','-shared','-fPIC',str(firmware/'rmc.c'),'-o',str(temp/'rmc.so')],check=True)
    library=ctypes.CDLL(str(temp/'rmc.so'))
    make=library.make_bench_rmc
    make.argtypes=[ctypes.c_uint32,ctypes.c_char_p,ctypes.c_size_t]; make.restype=ctypes.c_int
    for stamp in ['2026-11-23T00:00:00','2026-11-23T23:59:59','2026-11-24T00:00:00',
                  '2026-12-31T23:59:59','2027-01-01T00:00:00','2028-02-28T23:59:59',
                  '2028-02-29T00:00:00','2028-03-01T00:00:00','2100-03-01T00:00:00']:
        dt=datetime.fromisoformat(stamp).replace(tzinfo=timezone.utc)
        buf=ctypes.create_string_buffer(96)
        n=make(int(dt.timestamp()),buf,96)
        assert n>0
        text=buf.value.decode(); body,crc=text[1:].strip().split('*'); fields=body.split(',')
        assert fields[1]==dt.strftime('%H%M%S')+'.00',text
        assert fields[9]==dt.strftime('%d%m%y'),text
        check=0
        for ch in body: check^=ord(ch)
        assert check==int(crc,16),text
    assert make(1795392000,ctypes.create_string_buffer(4),4)==-1
    print('PASS: actual firmware RMC checksum, date/day/year/leap-year rollover and bounded buffer')
    exe=temp/'sdk-reference'
    subprocess.run(['g++','-std=c++14','-I'+str(sdk/'sdk_core'),'-I'+str(sdk/'3rdparty'),
                    str(here/'sdk_packet_reference.cpp'),str(sdk/'sdk_core/comm/sdk_protocol.cpp'),
                    str(sdk/'3rdparty/FastCRC/FastCRCsw.cpp'),'-o',str(exe)],check=True)
    golden=subprocess.check_output([str(exe)],text=True).strip()
    (here/'sdk-golden.json').write_text(json.dumps({'source':'Livox-SDK2 SdkProtocol::Pack + CheckPreamble',
        'sdk_commit':subprocess.check_output(['git','-C',str(sdk),'rev-parse','HEAD'],text=True).strip(),
        'hex':golden},indent=2)+'\n')
    print('PASS: upstream SDK2 packet generated and checked:',golden)
