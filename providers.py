"""On-demand text bridges. No persistent daemon, clipboard mutation or network."""
import json,os,re,shutil,subprocess,time
from pathlib import Path

ROOT=Path(os.environ.get('XDG_RUNTIME_DIR',f'/run/user/{os.getuid()}'))/'omalink'
CONFIG=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'omalink'


def process_started(pid):
    try:
        raw=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
        ticks=int(raw[19]); boot=next(int(l.split()[1]) for l in Path('/proc/stat').read_text().splitlines() if l.startswith('btime '))
        return boot+ticks/os.sysconf('SC_CLK_TCK')
    except (OSError,ValueError,StopIteration): return 0


def eligible(window):
    pid=window.get('pid',0); kind=window.get('class','').lower()
    if kind=='foot':
        ready=CONFIG/'foot-enabled-at'
        try:
            if ready.exists() and process_started(pid)>float(ready.read_text()): return 'foot'
        except (OSError,ValueError): pass
    if kind in {'google-chrome','google-chrome-stable'}:
        try:
            # Chrome rewrites argv and can clear /proc's environment view.
            command=Path(f'/proc/{pid}/cmdline').read_bytes().decode().replace('\0',' ')
            if re.search(r'(?:^|\s)--force-renderer-accessibility(?:\s|$)',command): return 'chrome'
        except (OSError,ValueError): pass
    return None


def parents():
    result=[]; pid=os.getppid()
    for _ in range(12):
        if pid<=1: break
        result.append(pid)
        try: pid=int(Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[1])
        except (OSError,ValueError): break
    return result


def deliver(payload,source):
    """Only answer a current request from the same owning application process."""
    try:
        request=json.loads((ROOT/'direct-request.json').read_text())
        if time.time()-request['at']>2 or request['pid'] not in parents() or request['provider']!=source: return False
        token=request['token']
        if not isinstance(token,str) or len(token)!=32 or any(c not in '0123456789abcdef' for c in token): return False
        response={'text':str(payload.get('text',''))[:131072],
                  'links':[v for v in payload.get('links',[])[:1000] if isinstance(v,str)],'source':source}
        temp=ROOT/token/'response.tmp'; target=ROOT/token/'response.json'
        temp.write_text(json.dumps(response)); temp.chmod(0o600); temp.replace(target)
        return True
    except (OSError,ValueError,KeyError,TypeError): return False


def direct(window,provider,token,timeout=0.35):
    if provider=='chrome':
        try:
            result=subprocess.run(['/usr/bin/python3',str(Path(__file__).with_name('accessibility.py')),str(int(window['pid']))],capture_output=True,text=True,check=True,timeout=.65)
            return json.loads(result.stdout)
        except (OSError,ValueError,subprocess.SubprocessError): return None
    address=window['address']
    if not re.fullmatch(r'0x[0-9a-fA-F]+',address) or not re.fullmatch(r'[0-9a-f]{32}',token): return None
    directory=ROOT/token
    directory.mkdir(mode=0o700)
    request=ROOT/'direct-request.json'; response=directory/'response.json'
    try:
        request.write_text(json.dumps({'pid':window['pid'],'address':address,'at':time.time(),'provider':provider,'token':token}))
        request.chmod(0o600)
        # Explicit target and explicit modifiers prevent held SUPER from leaking
        # into the bridge chord. Both edges are sent even if the wait fails.
        def edge(state):
            expression='hl.dsp.send_key_state({ mods = "ALT SHIFT", key = "U", state = "'+state+'", window = "address:'+address+'" })'
            subprocess.run(['hyprctl','dispatch',expression],capture_output=True,timeout=0.2,check=True)
        try: edge('down')
        finally: edge('up')
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if response.exists(): return json.loads(response.read_text())
            time.sleep(0.005)
    except (OSError,ValueError,subprocess.SubprocessError): return None
    finally:
        request.unlink(missing_ok=True)
        # Late native hosts cannot recreate the removed response directory.
        shutil.rmtree(directory,ignore_errors=True)
    return None

