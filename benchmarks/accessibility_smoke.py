#!/usr/bin/python3
"""Verify native Chrome text extraction in a disposable isolated profile."""
import functools,http.server,json,os,signal,subprocess,sys,tempfile,threading,time,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import omalink,providers
omalink.runtime()
class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args): pass
with tempfile.TemporaryDirectory(prefix='omalink-ax-',dir=os.environ['XDG_RUNTIME_DIR']) as tmp:
    root=Path(tmp); (root/'index.html').write_text('''<html><body><p>https://example.com/printed</p><a href="https://example.org/hidden">Label</a><a style="display:none" href="https://example.net/hidden">hidden</a><input value="https://example.net/input"><div style="position:absolute;top:100000px"><a href="https://example.net/offscreen">offscreen</a></div><div id="shadow"></div><script>document.querySelector('#shadow').attachShadow({mode:'open'}).innerHTML='<a href="https://example.org/shadow">Shadow link</a>';</script></body></html>''')
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=tmp))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    proc=subprocess.Popen([str(Path.home()/'.local/share/omalink/bin/google-chrome-stable'),'--user-data-dir='+tmp+'/profile','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-sync','http://127.0.0.1:'+str(server.server_port)+'/'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    try:
        window=None
        for _ in range(60):
            window=next((w for w in json.loads(subprocess.check_output(['hyprctl','clients','-j'])) if w['pid']==proc.pid),None)
            if window: break
            time.sleep(.05)
        assert window,'Test window missing'
        time.sleep(1)
        assert providers.eligible(window)=='chrome',(window['class'],[x for x in Path(f'/proc/{proc.pid}/environ').read_bytes().split(b'\0') if b'ACCESSIBILITY' in x])
        samples=[]
        for _ in range(3):
            start=time.perf_counter(); result=providers.direct(window,'chrome',uuid.uuid4().hex); samples.append((time.perf_counter()-start)*1000)
            assert result,'No accessibility result'
            urls=omalink.collect(result['text'],result['links'])['urls']
            assert set(urls)=={'https://example.com/printed','https://example.org/hidden','https://example.org/shadow'},urls
        omalink.capture()
        status=json.loads(omalink.run(['omarchy-shell','omalink','status']).stdout)
        assert status['links']==3 and not status['scanning'] and status['note'].startswith('chrome text'),status
        print(json.dumps({'provider':'chrome accessibility','samples_ms':samples,'urls':3,'panel':status,'checks':['printed URL','hidden href','shadow DOM','offscreen excluded','display:none excluded','editable excluded']}))
    finally:
        subprocess.run(['omarchy-shell','shell','hide',omalink.PLUGIN],stdout=subprocess.DEVNULL)
        os.killpg(proc.pid,signal.SIGTERM); proc.wait(timeout=5); server.shutdown()
