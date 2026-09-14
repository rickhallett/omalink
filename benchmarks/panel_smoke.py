#!/usr/bin/python3
"""Exercise OCR caching and latest-request-wins behaviour through real QML IPC."""
import json,os,subprocess,sys,tempfile,time,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import omalink
omalink.runtime(); captures=[]
def ipc(*args): return omalink.run(['omarchy-shell',*args]).stdout
def status(): return json.loads(ipc('omalink','status'))
def summon(p): ipc('shell','summon',omalink.PLUGIN,json.dumps(p))
def until(test,timeout=12):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        s=status()
        if test(s): return s
        time.sleep(.03)
    raise AssertionError(status())
def image(data):
    p=omalink.RUNTIME/('capture-'+uuid.uuid4().hex+'.png'); p.write_bytes(data); captures.append(p); return str(p)
with tempfile.TemporaryDirectory(prefix='omalink-panel-',dir=os.environ['XDG_RUNTIME_DIR']) as tmp:
    p=Path(tmp)/'fixture.png'; font=subprocess.check_output(['fc-match','-f','%{file}','monospace'],text=True)
    command=['magick','-size','1701x1390','xc:#181818','-font',font,'-pointsize','24','-fill','#eeeeee']
    # Dense enough to exercise asynchronous replacement, with known synthetic text.
    command+=['-annotate','+40+80','https://example.com/panel','-annotate','+40+140','https://docs.python.org/3/']
    for y in range(250,1350,45): command+=['-annotate','+40+'+str(y),'Synthetic fixture filler words '+uuid.uuid4().hex]
    subprocess.run(command+[str(p)],check=True); data=p.read_bytes()
    try:
        a=image(data); summon({'image':a,'scope':'window','captureMs':10})
        cold=until(lambda s:not s['scanning'] and s['links']>0)
        assert cold['note'].startswith('window OCR'),cold
        b=image(data); summon({'image':b,'scope':'window','captureMs':10})
        warm=until(lambda s:not s['scanning'] and s['links']>0)
        assert warm['note'].startswith('cached window OCR'),warm
        # Remove only this synthetic result's cache entry to force in-flight work.
        import hashlib
        cache=omalink.RUNTIME/'cache'/(hashlib.sha256(data+b'ocr-v4:1:eng:11').hexdigest()+'.json')
        cache.unlink(missing_ok=True)
        a=image(data); summon({'image':a}); time.sleep(.05)
        summon({'urls':['https://example.org/latest-1','https://example.org/latest-2'],'note':'latest direct result'})
        until(lambda s:not Path(a).exists())
        newest=status(); assert newest['links']==2 and newest['note']=='latest direct result',newest
        cache.unlink(missing_ok=True)
        a=image(data); b=image(data); summon({'image':a}); time.sleep(.05); summon({'image':b,'scope':'monitor'})
        queued=until(lambda s:not s['scanning'] and s['links']>0)
        assert 'monitor OCR' in queued['note'],queued
        cache.unlink(missing_ok=True)
        a=image(data); summon({'image':a}); time.sleep(.05); ipc('shell','hide',omalink.PLUGIN)
        closed=until(lambda s:not Path(a).exists()); assert not closed['opened'],closed
        print(json.dumps({'checks':['cold OCR','identical capture cache','stale OCR cannot overwrite direct result','latest queued capture wins','closing does not reopen'],'cold':cold['note'],'warm':warm['note']}))
    finally:
        ipc('shell','hide',omalink.PLUGIN)
        for p in captures: p.unlink(missing_ok=True)
