"""ST-LINK access: backup/read; writes only the verified firmware request word."""
from pathlib import Path
import sys,re,json,argparse,hashlib
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stm32/tools/pyocd'))
from intelhex import IntelHex
from pyocd.core.helpers import ConnectHelper
from pyocd.coresight.ap import APv1Address

class JointMCU:
    def __init__(self,verify=True):
        self.session=ConnectHelper.session_with_chosen_probe(unique_id='37FF71064E5734361EFA1A43',
            target_override='cortex_m',options={'connect_mode':'attach','auto_unlock':False,
            'resume_on_disconnect':False,'frequency':1000000,'cache.read_memory':False})
        if self.session is None: raise RuntimeError('ST-LINK unavailable')
        try:
            self.session.open(init_board=False)
            p=self.session.probe; p.connect(); p.write_dp(0x04,0x50000000)
            self.mem=p.get_memory_interface_for_ap(APv1Address(0))
            build=ROOT/'stm32/joint-sync-test/build'
            text=(build/'joint-sync-test.map').read_text()
            names=['pps_count','rmc_sent_count','firmware_fault','hse_ready',
                   'camera_request','camera_state','camera_pulses','camera_epoch']
            self.symbols={n:int(re.search(r'^\s*'+n+r'\s+(0x[0-9a-fA-F]+)\s+Data',text,re.M)[1],16) for n in names}
            if any(not 0x20000000<=a<0x20005000 for a in self.symbols.values()):
                raise RuntimeError('Invalid firmware RAM symbols')
            if verify:
                ih=IntelHex(str(build/'joint-sync-test.hex'))
                data=bytes(ih.tobinarray())
                if ih.minaddr()!=0x08000000 or ih.maxaddr()>=0x08010000:
                    raise RuntimeError('Image outside 64 KiB Flash')
                if bytes(self.mem.read_memory_block8(0x08000000,len(data)))!=data:
                    raise RuntimeError('Joint firmware Flash readback does not match built image')
        except BaseException:
            self.close(); raise
    def status(self):
        result={n:self.mem.read32(a) for n,a in self.symbols.items()}
        result['dhcsr']=self.mem.read32(0xE000EDF0)
        return result
    def request(self,action):
        state=self.status()
        if state['firmware_fault'] or not state['hse_ready'] or state['dhcsr']&(1<<17):
            raise RuntimeError('MCU not running with valid HSE: '+str(state))
        if action=='arm' and state['camera_state'] not in (0,3):
            raise RuntimeError('Camera batch already active')
        self.mem.write32(self.symbols['camera_request'],{'arm':0x43414D35,'stop':0x53544F50}[action])
    def close(self): self.session.close()

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('action',choices=['backup','status','arm','stop','start'])
    args=ap.parse_args(); m=JointMCU(verify=args.action!='backup')
    try:
        if args.action=='backup':
            data=bytes(m.mem.read_memory_block8(0x08000000,65536))
            folder=ROOT/'stm32'/('before-joint-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
            folder.mkdir(); (folder/'flash-64k.bin').write_bytes(data)
            print(json.dumps({'path':str(folder),'sha256':hashlib.sha256(data).hexdigest()}))
        else:
            if args.action=='start':
                # Only used after verified flashing, before a new sync session.
                m.mem.write32(0xE000ED0C,0x05FA0004)
                import time
                time.sleep(1.2)
            elif args.action!='status': m.request(args.action)
            print(json.dumps(m.status()))
    finally: m.close()
