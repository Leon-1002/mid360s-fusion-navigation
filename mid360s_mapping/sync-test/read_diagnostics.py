"""Read and save radar diagnostics only. No configuration or time writes."""
import json
import struct
from pathlib import Path
from datetime import datetime
from run_sync import Network
from livox_wire import query_payload,parse_values

net=Network('192.168.1.50','192.168.1.119')
try:
    values=parse_values(net.request(0x0101,query_payload((0x8006,0x8007,0x800E,0x8002,0x8011))))
finally:
    net.close()
report={'raw':{hex(k):v.hex() for k,v in values.items()}}
if 0x8006 in values: report['work_state']=int.from_bytes(values[0x8006],'little')
if 0x8007 in values: report['core_temperature_c']=int.from_bytes(values[0x8007],'little',signed=True)/100
if 0x800E in values:
    code=int.from_bytes(values[0x800E],'little')
    report['diag_status']=hex(code)
    report['module_levels']={name:(code>>shift)&15 for name,shift in [('system',0),('scan',4),('ranging',8),('communication',12)]}
if 0x8011 in values:
    data=values[0x8011]
    report['hms_codes']=[hex(x[0]) for x in struct.iter_unpack('<I',data) if x[0]]
folder=Path(__file__).parent/'sessions'
folder.mkdir(exist_ok=True)
output=folder/('diagnostics-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2)); print(output)
