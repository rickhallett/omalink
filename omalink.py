#!/usr/bin/python3
"""Pick visible URLs using direct text or local OCR and open them in Chrome."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from urllib.parse import urlsplit, unquote

RUNTIME = Path(os.environ.get('XDG_RUNTIME_DIR',f'/run/user/{os.getuid()}'))/'omalink'
PLUGIN = 'ms02.omalink'
# Explicit schemes and www have broad host support; bare domains use common TLDs
# to avoid turning source filenames (app.py, main.rs) into links.
URL_PATTERN = re.compile(r'''https?://[^\s<>"`]+|www\.[^\s<>"`]+|(?<![\w@./-])(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+(?:com|org|net|io|ai|dev|app|co|uk|edu|gov|me|xyz|tech|sh|gg|info)(?::\d{1,5})?(?:/[^\s<>"`]*)?(?![\w.-])''',re.IGNORECASE)

IMAGE_EXTENSIONS = {'.png','.jpg','.jpeg','.webp','.gif','.bmp','.svg','.avif','.ico'}
GENERATED = Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'generated_images'
LOCAL_PATTERN = re.compile(r"file://[^\s<>\"`]+|(?<![\w:/])(?:~/|/)[^\s<>\"`]+",re.I)

def local_image(value):
    if value.startswith('file:'):
        uri=urlsplit(value)
        if uri.netloc not in {'','localhost'} or uri.query or uri.fragment:
            raise ValueError('Only local image file URLs are supported')
        value=unquote(uri.path)
    path=Path(value).expanduser()
    if not path.is_absolute() or path.suffix.lower() not in IMAGE_EXTENSIONS or not path.is_file():
        raise ValueError('Not an existing local image')
    return path.resolve().as_uri()

def recent_images(limit=5):
    if not GENERATED.is_dir(): return []
    images=[]
    for p in GENERATED.glob('*/*'):
        try:
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS:
                images.append((p.stat().st_mtime_ns,str(p)))
        except OSError: pass
    return [Path(p).resolve().as_uri() for _,p in sorted(images,reverse=True)[:limit]]

def validate(url):
    if any(c.isspace() or ord(c)<32 or ord(c)==127 for c in url): raise ValueError('URL contains whitespace or control characters')
    if url.startswith(('file:', '/', '~/')): return local_image(url)
    parsed=urlsplit(url)
    if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Only HTTP(S) URLs without embedded credentials are supported')
    if any(c in parsed.hostname for c in '<>"`\\') or '\\' in url: raise ValueError('Invalid URL')
    try: parsed.port
    except ValueError: raise ValueError('Invalid URL port') from None
    return url

def extract(text):
    # Repair only unambiguous spacing around the scheme, not arbitrary URL text.
    text=re.sub(r'\b(https?)\s*:\s*/\s*/\s*',r'\1://',text,flags=re.IGNORECASE)
    found=[]; seen=set()
    web_matches=list(URL_PATTERN.finditer(text))
    local_matches=[m for m in LOCAL_PATTERN.finditer(text)
                   if not any(w.start()<=m.start()<w.end() for w in web_matches)]
    # Quoted local paths may contain spaces; keep them intact.
    quoted=list(re.finditer(r"[\"']((?:~/|/)[^\"'\n]+)[\"']",text))
    local_matches=[m for m in local_matches if not any(q.start()<m.start()<q.end() for q in quoted)]
    candidates=[(m.start(),m.group(0)) for m in web_matches+local_matches]
    candidates += [(q.start(),q.group(1)) for q in quoted]
    for _, raw in sorted(candidates):
        if '…' in raw or '...' in raw: continue
        value=raw.rstrip('.,;:!?\'’”')
        for closing,opening in [(')', '('),(']', '['),('}', '{')]:
            while value.endswith(closing) and value.count(closing)>value.count(opening): value=value[:-1]
        if '…' in value or '...' in value: continue  # visibly truncated addresses cannot be reconstructed
        if value.startswith(('file:', '/', '~/')):
            try: value=local_image(value)
            except (ValueError,OSError): continue
        elif not re.match(r'https?://',value,re.I): value='https://'+value
        value=re.sub(r'^https?',lambda m:m.group(0).lower(),value,flags=re.I)
        try: validate(value)
        except ValueError: continue
        parsed=urlsplit(value)
        key=(parsed.scheme,parsed.netloc.lower(),parsed.path,parsed.query,parsed.fragment)
        if key not in seen:
            seen.add(key); found.append(value)
    return found

def run(args,**kwargs):
    return subprocess.run(args,check=True,capture_output=True,text=True,timeout=15,**kwargs)

def runtime():
    RUNTIME.mkdir(parents=True,exist_ok=True,mode=0o700)
    # Only captures from crashed prior invocations, never user files.
    for p in RUNTIME.glob('capture-*.png'):
        try:
            if time.time()-p.stat().st_mtime>300: p.unlink(missing_ok=True)
        except FileNotFoundError: pass
    for p in RUNTIME.iterdir():
        if re.fullmatch(r'[0-9a-f]{32}',p.name) and p.is_dir() and time.time()-p.stat().st_mtime>300:
            shutil.rmtree(p,ignore_errors=True)

def owned(path):
    p=Path(path)
    if p.parent!=RUNTIME or not re.fullmatch(r'capture-[a-zA-Z0-9_\-]+\.png',p.name) or p.is_symlink():
        raise ValueError('Not an omalink capture')
    return p

def config():
    path=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'omalink/config.json'
    settings={'scope':'window','threads':1,'cache_ttl_s':30,'direct':True}
    if path.exists(): settings.update(json.loads(path.read_text()))
    if settings['scope'] not in {'window','monitor'}: raise ValueError('scope must be window or monitor')
    if settings['threads'] not in {1,2,4}: raise ValueError('threads must be 1, 2 or 4')
    return settings


def collect(text,links=(),*,ocr=False):
    urls=extract(text)
    if ocr:
        # Single-label hosts are usually clipped OCR fragments (e.g. https://qithub).
        # Direct text and explicit open commands still support intranet hosts.
        urls=[u for u in urls if urlsplit(u).scheme=='file' or '.' in (urlsplit(u).hostname or '') or ':' in (urlsplit(u).hostname or '') or urlsplit(u).hostname=='localhost']
    # OSC-8 hyperlinks preserve destinations even when terminal labels hide them.
    for value in re.findall(r'\x1b\]8;[^;]*;([^\x07\x1b]+)',text)+list(links):
        try: value=validate(value)
        except (ValueError,OSError): continue
        if value not in urls: urls.append(value)
    return {'urls':urls,'image_marker':bool(re.search(r'\bImage\s*#\s*\d+',text,re.I))}


def decorate(data,source,elapsed_ms):
    urls=list(data['urls']); recent=recent_images() if data.get('image_marker') else []
    for value in recent:
        if value not in urls: urls.append(value)
    note=f'{source} · {round(elapsed_ms)} ms'
    if recent: note+=' · Image labels: local images are recent candidates, not resolved destinations.'
    return {'urls':urls,'note':note,'source':source,'elapsed_ms':round(elapsed_ms,2)}


def metric(record):
    # No screenshot, title, path, OCR text or URL content in performance records.
    runtime()
    path=RUNTIME/'timings.jsonl'
    if path.exists() and path.stat().st_size>256000: path.unlink()
    with path.open('a') as stream: stream.write(json.dumps(record)+'\n')
    path.chmod(0o600)


def geometry(window,monitor):
    scale=monitor.get('scale',1)
    # Hyprland window coordinates and grim -g both use logical layout units.
    mw,mh=monitor['width']/scale,monitor['height']/scale
    if monitor.get('transform',0) in {1,3,5,7}: mw,mh=mh,mw
    mx,my=monitor['x'],monitor['y']; x,y=window['at']; w,h=window['size']
    left=max(mx,x); top=max(my,y); right=min(mx+mw,x+w); bottom=min(my+mh,y+h)
    if right<=left or bottom<=top: raise ValueError('Focused window does not intersect its monitor')
    return f'{round(left)},{round(top)} {round(right-left)}x{round(bottom-top)}'


def capture(scope=None):
    import uuid
    import providers
    settings=config(); scope=scope or settings['scope']
    runtime(); start=time.perf_counter()
    with (RUNTIME/'capture.lock').open('w') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return
        monitors=json.loads(run(['hyprctl','monitors','-j']).stdout)
        monitor=next((m for m in monitors if m.get('focused')),None)
        if not monitor: raise ValueError('No focused monitor')
        window=json.loads(run(['hyprctl','activewindow','-j']).stdout)
        if not window.get('mapped') or not window.get('size'): scope='monitor'
        run(['omarchy-shell','shell','hide',PLUGIN])
        provider=providers.eligible(window) if scope=='window' and settings['direct'] else None
        if scope=='window' and settings['direct'] and window.get('class','').lower()=='foot' and provider is None:
            # Older Foot processes cannot reload pipe-visible. Their built-in
            # URL mode uses original text, without guessing URLs from pixels.
            providers.foot_url_mode(window)
            metric({'source':'foot native hints','total_ms':round((time.perf_counter()-start)*1000,2)})
            return
        if provider:
            data=providers.direct(window,provider,uuid.uuid4().hex)
            if data:
                result=collect(data.get('text',''),data.get('links',[]))
                if result['urls'] or result['image_marker']:
                    result=decorate(result,provider+' text',(time.perf_counter()-start)*1000)
                    metric({'source':result['source'],'total_ms':result['elapsed_ms'],'links':len(result['urls'])})
                    run(['omarchy-shell','shell','summon',PLUGIN,json.dumps({**result,'monitor':monitor['name']})])
                    return
        # Allow the old picker to finish its 140 ms fade, if one was open.
        time.sleep(max(0,0.16-(time.perf_counter()-start)))
        with tempfile.NamedTemporaryFile(prefix='capture-',suffix='.png',dir=RUNTIME,delete=False) as temp:
            path=Path(temp.name)
        try:
            command=['grim','-l','0']
            if scope=='window': command+=['-g',geometry(window,monitor),'-s',str(monitor.get('scale',1))]
            else: command+=['-o',monitor['name']]
            run(command+[str(path)])
            elapsed=(time.perf_counter()-start)*1000
            payload={'image':str(path),'monitor':monitor['name'],'scope':scope,'captureMs':elapsed}
            run(['omarchy-shell','shell','summon',PLUGIN,json.dumps(payload)])
        except Exception:
            path.unlink(missing_ok=True); raise


def ocr(path,scope='window',capture_ms=0):
    import hashlib
    path=owned(path); started=time.perf_counter(); settings=config()
    cache=RUNTIME/'cache'; cache.mkdir(parents=True,exist_ok=True,mode=0o700)
    ttl=max(0,min(300,float(settings['cache_ttl_s'])))
    try:
        entries=sorted(cache.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)
        for i,p in enumerate(entries):
            if i>=16 or time.time()-p.stat().st_mtime>ttl: p.unlink(missing_ok=True)
        digest=hashlib.sha256(path.read_bytes()+f'ocr-v4:{settings["threads"]}:eng:11'.encode()).hexdigest()
        entry=cache/(digest+'.json'); data=None
        if entry.exists() and ttl:
            try:
                candidate=json.loads(entry.read_text())
                if isinstance(candidate,dict) and isinstance(candidate.get('urls'),list) and all(isinstance(u,str) for u in candidate['urls']): data=candidate
            except (OSError,ValueError): pass
        cached=data is not None
        if data is None:
            result=run(['tesseract',str(path),'stdout','--oem','1','--psm','11','-l','eng','--dpi','150'],env={**os.environ,'OMP_THREAD_LIMIT':str(settings['threads'])})
            data=collect(result.stdout,ocr=True)
            if ttl:
                with tempfile.NamedTemporaryFile(mode='w',prefix='entry-',suffix='.tmp',dir=cache,delete=False) as stream:
                    json.dump(data,stream); temporary=Path(stream.name)
                temporary.replace(entry)
        elapsed=(time.perf_counter()-started)*1000+capture_ms
        result=decorate(data,('cached ' if cached else '')+scope+' OCR',elapsed)
        result['note']+=' · Check destinations: OCR can misread links.'
        metric({'source':result['source'],'total_ms':result['elapsed_ms'],'capture_ms':capture_ms,'links':len(result['urls'])})
        return result
    finally: path.unlink(missing_ok=True)


def chrome_command(url):
    url=validate(url)
    chrome=shutil.which('google-chrome-stable') or shutil.which('google-chrome')
    if not chrome: raise ValueError('Google Chrome is not installed')
    bridge=Path.home()/'.local/share/omalink/bin/google-chrome-stable'
    if bridge.is_file(): chrome=str(bridge)
    return ['systemd-run','--user','--quiet','--collect',f'--unit=omalink-chrome-{time.time_ns()}',
            '--property=StandardOutput=null','--property=StandardError=null','uwsm-app','--',chrome,'--new-tab',url]

def open_url(url):
    command=chrome_command(url)
    clients=json.loads(run(['hyprctl','clients','-j']).stdout)
    chrome=[c for c in clients if re.fullmatch(r'google-chrome(?:-stable)?',c.get('class',''),re.I)]
    if chrome:
        target=min(chrome,key=lambda c:c.get('focusHistoryID',999999) if c.get('focusHistoryID',-1)>=0 else 999999)
        address=target['address']
        if re.fullmatch(r'0x[0-9a-fA-F]+',address):
            run(['hyprctl','dispatch','hl.dsp.focus({ window = "address:'+address+'" })'])
    run(command)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command')
    p=sub.add_parser('capture'); p.add_argument('--monitor',action='store_true'); sub.add_parser('demo')
    sub.add_parser('from-stdin')
    for name,arg in [('ocr','path'),('discard','path'),('open','url')]:
        p=sub.add_parser(name); p.add_argument(arg)
        if name=='ocr': p.add_argument('--scope',choices=['window','monitor'],default='window'); p.add_argument('--capture-ms',type=float,default=0)
    p=sub.add_parser('extract'); p.add_argument('text')
    args=parser.parse_args()
    if not args.command: parser.print_help(); return
    if args.command=='capture': capture('monitor' if args.monitor else None)
    elif args.command=='ocr': print(json.dumps(ocr(args.path,args.scope,args.capture_ms)))
    elif args.command=='from-stdin':
        import sys,providers
        providers.deliver({'text':sys.stdin.read(131072)},'foot')
    elif args.command=='discard': owned(args.path).unlink(missing_ok=True)
    elif args.command=='open': open_url(args.url)
    elif args.command=='extract': print(json.dumps(extract(args.text)))
    elif args.command=='demo':
        run(['omarchy-shell','shell','summon',PLUGIN,json.dumps({'urls':['https://github.com/rickhallett/omatag','https://docs.python.org/3/','https://doc.qt.io/qt-6/qmlapplications.html']})])

if __name__=='__main__':
    try: main()
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        import sys
        message=('Command timed out' if isinstance(error,subprocess.TimeoutExpired) else 'Desktop command failed: '+str(error.cmd[0])) if isinstance(error,subprocess.SubprocessError) else str(error)
        print(message,file=sys.stderr)
        sys.exit(1)
