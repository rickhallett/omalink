import json,os,signal,subprocess,sys,tempfile,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import omalink,providers
with tempfile.TemporaryDirectory(prefix='omalink-native-') as tmp:
 root=Path(tmp); output=root/'selected'; script=root/'record.py'
 script.write_text('import sys\nfrom pathlib import Path\nPath(sys.argv[1]).write_text(sys.argv[2])\n')
 expected='https://github.com/rickhallett/omalink'
 proc=subprocess.Popen(['foot','--title=omalink native verification','-o',f'url.launch=/usr/bin/python3 {script} {output} ${{url}}','/usr/bin/python3','-c',f'import time; print({expected!r},flush=True); time.sleep(20)'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,start_new_session=True)
 try:
  window=None
  for _ in range(40):
   window=next((w for w in json.loads(subprocess.check_output(['hyprctl','clients','-j'])) if w['pid']==proc.pid),None)
   if window:break
   time.sleep(.05)
  assert window,proc.stderr.read().decode()
  time.sleep(.2)
  with patch.object(providers,'eligible',return_value=None):omalink.capture()
  time.sleep(.15)
  for state in ['down','up']:
   subprocess.run(['hyprctl','dispatch','hl.dsp.send_key_state({ mods = "", key = "S", state = "'+state+'", window = "address:'+window['address']+'" })'],capture_output=True,check=True)
  for _ in range(30):
   if output.exists():break
   time.sleep(.05)
  assert output.exists(),'Native hint did not select a URL'
  assert output.read_text()==expected,output.read_text()
  print('PASS: older-Foot fallback selected the exact fixture URL; no browser launched')
 finally:
  os.killpg(proc.pid,signal.SIGTERM);proc.wait(timeout=3)
