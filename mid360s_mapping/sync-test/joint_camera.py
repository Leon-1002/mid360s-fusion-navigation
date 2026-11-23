"""Native Windows IMV capture, with reversible feature settings."""
import os,sys,time,ctypes,json
from pathlib import Path
SDK=Path('E:/MVviewer/MV Viewer')
os.environ['PATH']=str(SDK/'Runtime/x64')+os.pathsep+os.environ['PATH']
_dll_dir=os.add_dll_directory(str(SDK/'Runtime/x64'))
_legacy_sdk=ctypes.WinDLL(str(SDK/'Runtime/x64/MVSDKmd.dll'),winmode=0)
sys.path.insert(0,str(SDK/'Development/Samples/Python/IMV/MVSDK'))
_cwd=os.getcwd()
try:
    os.chdir(SDK/'Development/Samples/Python/IMV/SoftTrigger')
    import IMVApi as api
finally: os.chdir(_cwd)

def checked(code,action):
    if code!=0: raise RuntimeError(f'{action}: SDK error {code}')

class Camera:
    def __init__(self,folder):
        self.folder=Path(folder); self.cam=api.MvCamera()
        self.created=False; self.opened=False; self.grabbing=False
        self.undo=[]; self.before={}
        self.unsuccessful_fetches=[]
    def open(self):
        devices=api.IMV_DeviceList()
        checked(api.MvCamera.IMV_EnumDevices(devices,api.IMV_EInterfaceType.interfaceTypeAll),'enumerate')
        matches=[i for i in range(devices.nDevNum) if devices.pDevInfo[i].serialNumber.decode()=='DD07657AAK00023']
        if len(matches)!=1: raise RuntimeError(f'Expected camera absent; enumerated {devices.nDevNum}')
        checked(self.cam.IMV_CreateHandle(api.IMV_ECreateHandleMode.modeByIndex,ctypes.byref(ctypes.c_uint(matches[0]))),'create')
        self.created=True
        checked(self.cam.IMV_Open(),'open'); self.opened=True
    def get(self,kind,name):
        types={'enum':api.IMV_String,'float':ctypes.c_double,'int':ctypes.c_int64,'bool':ctypes.c_bool}
        methods={'enum':'IMV_GetEnumFeatureSymbol','float':'IMV_GetDoubleFeatureValue',
                 'int':'IMV_GetIntFeatureValue','bool':'IMV_GetBoolFeatureValue'}
        val=types[kind](); checked(getattr(self.cam,methods[kind])(name,val),'read '+name)
        return bytes(val.str).split(b'\0')[0].decode() if kind=='enum' else val.value
    def put(self,kind,name,value):
        methods={'enum':'IMV_SetEnumFeatureSymbol','float':'IMV_SetDoubleFeatureValue',
                 'int':'IMV_SetIntFeatureValue','bool':'IMV_SetBoolFeatureValue'}
        checked(getattr(self.cam,methods[kind])(name,value),'write '+name)
    def change(self,kind,name,value):
        old=self.get(kind,name); self.before.setdefault(name,old)
        if old!=value:
            self.undo.append((kind,name,old))
            self.put(kind,name,value)
        actual=self.get(kind,name)
        if actual!=value: raise RuntimeError(f'{name} readback {actual!r} != {value!r}')
        (self.folder/'camera-settings-before.json').write_text(json.dumps(self.before,indent=2))
    def configure(self):
        self.change('enum','TriggerSelector','FrameStart')
        self.change('enum','TriggerMode','Off')
        self.change('enum','LineSelector','Line2')
        self.change('enum','LineMode','Input')
        self.change('bool','LineInverter',False)
        self.change('enum','TriggerSource','Line2')
        self.change('enum','TriggerMode','On')
        self.change('enum','TriggerActivation','RisingEdge')
        self.change('enum','AcquisitionMode','Continuous')
        for name in ('ExposureAuto','GainAuto'):
            if self.cam.IMV_FeatureIsAvailable(name): self.change('enum',name,'Off')
        self.change('float','ExposureTime',30000.0)
        self.change('float','GainRaw',2.0)
        self.change('enum','PixelFormat','BayerRG8')
        self.change('int','Width',3072); self.change('int','Height',2048)
        self.change('enum','TriggerMode','On')
        checked(self.cam.IMV_StartGrabbing(),'start grabbing'); self.grabbing=True
    def frame(self,timeout=100):
        frame=api.IMV_Frame(); code=self.cam.IMV_GetFrame(frame,timeout)
        if code!=0:
            # Installed Development/Include/IMV/IMVDefines.h defines -119 as
            # IMV_TIMEOUT; the bundled Python constants omit newer codes.
            self.unsuccessful_fetches.append({'code':code,'host_monotonic':time.monotonic()})
            if code==-119: return None
            raise RuntimeError(f'get frame: SDK error {code}')
        try:
            info=frame.frameInfo
            return {k:int(getattr(info,k)) for k in ('blockId','status','width','height','size','pixelFormat','timeStamp')} | {'host_monotonic':time.monotonic()}
        finally: checked(self.cam.IMV_ReleaseFrame(frame),'release frame')
    def close(self):
        errors=[]
        if self.grabbing:
            ret=self.cam.IMV_StopGrabbing()
            if ret: errors.append(f'stop grabbing: {ret}')
            self.grabbing=False
        if self.opened:
            for kind,name,old in reversed(self.undo):
                try:
                    self.put(kind,name,old)
                    if self.get(kind,name)!=old: raise RuntimeError('readback differs')
                except RuntimeError as e: errors.append(str(e))
            ret=self.cam.IMV_Close()
            if ret: errors.append(f'close camera: {ret}')
            self.opened=False
        if self.created:
            ret=self.cam.IMV_DestroyHandle()
            if ret: errors.append(f'destroy: {ret}')
            self.created=False
        return errors

if __name__=='__main__':
    # Read-only camera identification; never starts acquisition or writes settings.
    devices=api.IMV_DeviceList()
    checked(api.MvCamera.IMV_EnumDevices(devices,api.IMV_EInterfaceType.interfaceTypeAll),'enumerate')
    print(json.dumps([{'serial':devices.pDevInfo[i].serialNumber.decode(),
                       'model':devices.pDevInfo[i].modelName.decode()} for i in range(devices.nDevNum)]))
