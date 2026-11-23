"""Bounded concurrent camera + PPS/RMC bench test; no ROS or host-clock changes."""
import argparse,json,time,threading,statistics
from pathlib import Path
from datetime import datetime
from joint_mcu import JointMCU
from joint_camera import Camera
from run_sync import execute

def assess_frames(frames,pulses):
    gaps=sum(b['blockId']!=a['blockId']+1 for a,b in zip(frames,frames[1:]))
    reversed_ticks=sum(b['timeStamp']<=a['timeStamp'] for a,b in zip(frames,frames[1:]))
    bad=sum(f['status']!=0 or (f['width'],f['height'],f['size'],f['pixelFormat'])!=
            (3072,2048,3072*2048,0x01080009) for f in frames)
    elapsed=frames[-1]['host_monotonic']-frames[0]['host_monotonic'] if len(frames)>1 else 0
    rate=(len(frames)-1)/elapsed if elapsed>0 else 0
    ok=(len(frames)==300 and pulses==300 and not gaps and not reversed_ticks and not bad and 4.8<=rate<=5.2)
    return {'pass':ok,'frames':len(frames),'pulses':pulses,'frame_id_discontinuities':gaps,
            'camera_tick_non_increases':reversed_ticks,'invalid_frames':bad,'host_observed_fps':rate,
            'camera_tick_step_median':statistics.median([b['timeStamp']-a['timeStamp'] for a,b in zip(frames,frames[1:])]) if len(frames)>1 else None}

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--check-camera',action='store_true')
    parser.add_argument('--port',default='COM8'); args=parser.parse_args()
    folder=Path(__file__).parent/'sessions'/('joint-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    folder.mkdir(); log=(folder/'events.jsonl').open('w',encoding='utf-8')
    lock=threading.Lock(); radar_ready=threading.Event(); radar_done=threading.Event()
    radar={'mode':'sync','synthetic_time':True,'real_utc_valid':False,'rmc_count':0,
           'time_command_acks':0,'matched_status_count':0,'result':'NOT_COMPLETED'}
    summary={'result':'NOT_COMPLETED','synthetic_time':True,'real_utc_valid':False,
             'phase_measured_externally':False,'ros_transport_tested':False}
    cam=None; mcu=None; worker=None; frames=[]; cleanup=[]
    def emit(event,**data):
        row={'event':event,'host_monotonic':time.monotonic(),**data}
        with lock:
            log.write(json.dumps(row)+'\n'); log.flush()
            if event in ('session','ready','steady_window_started','camera_ready','camera_progress','error','stream_restore','summary'):
                print(json.dumps(row),flush=True)
        if event=='steady_window_started': radar_ready.set()
    def run_radar():
        try:
            execute(argparse.Namespace(mode='sync',host='192.168.1.50',lidar='192.168.1.119',
                                       port=args.port,seconds=75),emit,radar)
        except (OSError,ValueError,RuntimeError) as error:
            radar['result']='FAILED'; radar['error']=str(error); emit('error',source='radar',message=str(error))
        finally: radar_done.set()
    emit('session',path=str(folder))
    try:
        mcu=JointMCU(); before=mcu.status(); emit('mcu_before',**before)
        if before['camera_state'] not in (0,3) or before['firmware_fault'] or not before['hse_ready']:
            raise RuntimeError('MCU not ready for a new batch')
        cam=Camera(folder); cam.open(); cam.configure()
        if cam.frame(700) is not None: raise RuntimeError('Camera delivered a frame with PA1 idle; cannot establish trigger counting baseline')
        emit('camera_ready',serial='DD07657AAK00023',source='Line2',fps=5,exposure_us=30000,gain=2)
        if args.check_camera:
            summary['result']='CAMERA_READY_NO_PULSES'; return_code=0
        else:
            worker=threading.Thread(target=run_radar); worker.start()
            deadline=time.monotonic()+18
            while not radar_ready.wait(.1):
                if radar_done.is_set() or time.monotonic()>deadline:
                    raise RuntimeError('Radar failed to establish steady synchronization before camera arm')
            mcu.request('arm'); emit('camera_arm_requested')
            deadline=time.monotonic()+66; finished_at=None; last_report=0; state=mcu.status()
            while time.monotonic()<deadline:
                frame=cam.frame(100)
                if frame is not None:
                    frames.append(frame); emit('camera_frame',**frame)
                now=time.monotonic()
                state=mcu.status()
                if state['firmware_fault']: raise RuntimeError('MCU firmware fault')
                if radar_done.is_set() and radar.get('result')=='FAILED': raise RuntimeError('Radar test failed')
                if now-last_report>=5:
                    emit('camera_progress',received=len(frames),mcu=state); last_report=now
                if state['camera_state']==3:
                    if finished_at is None: finished_at=now
                    if now-finished_at>1.5: break
            summary['mcu_final']=state
            summary['camera']=assess_frames(frames,state['camera_pulses'])
            if state['camera_state']!=3: summary['camera']['pass']=False
            # Mapping is derived only if the entire bounded batch is complete.
            # It is not a measured exposure timestamp or real UTC.
            if summary['camera']['pass']:
                with (folder/'frame-trigger-correspondence.jsonl').open('w') as stream:
                    for i,frame in enumerate(frames):
                        stream.write(json.dumps({'block_id':frame['blockId'],'camera_ticks':frame['timeStamp'],
                            'scheduled_trigger_ns':state['camera_epoch']*10**9+190000000+i*200000000,
                            'timestamp_basis':'synthetic_timer_schedule_not_measured_exposure'})+'\n')
            worker.join(timeout=20)
            if worker.is_alive(): raise RuntimeError('Radar worker exceeded bounded test duration')
            summary['radar']=radar
            good_radar=radar['result'] in ('BENCH_SYNC_PASS','TIMING_PASS_CRC_UNAVAILABLE')
            summary['result']=('JOINT_TIMING_PASS_CRC_UNAVAILABLE' if radar['result']=='TIMING_PASS_CRC_UNAVAILABLE'
                              else 'JOINT_BENCH_PASS') if good_radar and summary['camera']['pass'] else 'JOINT_FAILED'
            return_code=0 if summary['result']=='JOINT_BENCH_PASS' else 3 if summary['result']=='JOINT_TIMING_PASS_CRC_UNAVAILABLE' else 2
    except (OSError,ValueError,RuntimeError) as error:
        summary['result']='JOINT_FAILED'; summary['error']=str(error)
        emit('error',source='joint',message=str(error)); return_code=2
    finally:
        if mcu:
            try:
                state=mcu.status()
                if state['camera_state'] in (1,2):
                    mcu.request('stop')
                    time.sleep(.1)
                    if mcu.status()['camera_state'] in (1,2): raise RuntimeError('Camera pulse stop not confirmed')
            except (OSError,ValueError,RuntimeError) as error: cleanup.append('MCU stop: '+str(error))
            mcu.close()
        if cam:
            summary['unsuccessful_frame_fetches']=cam.unsuccessful_fetches
            cleanup.extend(cam.close())
        if worker and worker.is_alive():
            worker.join(timeout=85)
            if worker.is_alive(): cleanup.append('Radar worker still running')
        summary['radar']=radar; summary['cleanup_errors']=cleanup
        if cleanup: summary['result']='RESTORE_FAILED'; return_code=2
        (folder/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        emit('summary',**summary); log.close()
        print('Report:',folder,flush=True)
    return return_code

if __name__=='__main__': raise SystemExit(main())
