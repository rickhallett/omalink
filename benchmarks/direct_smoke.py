#!/usr/bin/python3
import json,os,signal,subprocess,sys,time,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import omalink,providers
omalink.runtime()
code="import time; print('https://example.com/terminal\\nhttps://docs.python.org/3/',flush=True); time.sleep(30)"
proc=subprocess.Popen(['foot','--title=omalink verification','/usr/bin/python3','-c',code],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,start_new_session=True)
try:
    window=None
    for _ in range(40):
        windows=json.loads(subprocess.check_output(['hyprctl','clients','-j']))
        window=next((w for w in windows if w['pid']==proc.pid),None)
        if window: break
        time.sleep(0.05)
    assert window,'Test Foot window did not open'
    time.sleep(0.2)
    assert providers.eligible(window)=='foot',window['pid']
    times=[]
    for _ in range(3):
        start=time.perf_counter(); data=providers.direct(window,'foot',uuid.uuid4().hex,timeout=0.5)
        times.append((time.perf_counter()-start)*1000)
        assert data,'No terminal pipe response'
        assert omalink.collect(data['text'])['urls']==['https://example.com/terminal','https://docs.python.org/3/'],repr(data)
    omalink.capture()
    status=json.loads(omalink.run(['omarchy-shell','omalink','status']).stdout)
    assert status['links']==2 and not status['scanning'] and status['note'].startswith('foot text'),status
    print(json.dumps({'provider':'foot','samples_ms':times,'urls':2,'panel':status}))
finally:
    subprocess.run(['omarchy-shell','shell','hide',omalink.PLUGIN],stdout=subprocess.DEVNULL)
    os.killpg(proc.pid,signal.SIGTERM)
    proc.wait(timeout=3)
