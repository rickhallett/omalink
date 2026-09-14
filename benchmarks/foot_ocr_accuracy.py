import subprocess,tempfile,time,os,signal,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import omalink
urls=['https://github.com/rickhallett/omalink','https://rickhallett.github.io/omalink/','https://example.com/minimum/naming','https://example.net/common/mnemonic','https://omarchy.org/manual/','https://example.com/?name=minimum&mode=normal']
with tempfile.TemporaryDirectory(prefix='omalink-foot-accuracy-') as tmp:
 root=Path(tmp);raw=root/'raw.png'
 content='Omalink OCR accuracy fixture\n\n'+ '\n\n'.join(urls)+'\n\nEnd of fixture.'
 proc=subprocess.Popen(['foot','--title=omalink accuracy fixture','/usr/bin/python3','-c',f'import time;print({content!r},flush=True);time.sleep(40)'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,start_new_session=True)
 try:
  for _ in range(40):
   window=next((w for w in json.loads(subprocess.check_output(['hyprctl','clients','-j'])) if w['pid']==proc.pid),None)
   if window:break
   time.sleep(.05)
  assert window
  time.sleep(.2)
  monitor=next(m for m in json.loads(subprocess.check_output(['hyprctl','monitors','-j'])) if m['id']==window['monitor'])
  subprocess.run(['grim','-g',omalink.geometry(window,monitor),'-s',str(monitor['scale']),str(raw)],check=True)
  for name,args in [('raw',[]),('2x',['-resize','200%'])]:
   p=root/(name+'.png');subprocess.run(['magick',str(raw)]+args+[str(p)],check=True)
   for psm in ['11']:
    t=time.perf_counter();r=subprocess.run(['tesseract',str(p),'stdout','--oem','1','--psm',psm,'-l','eng','--dpi','150'],capture_output=True,text=True,check=True,env={**os.environ,'OMP_THREAD_LIMIT':'1'})
    found=omalink.collect(r.stdout,ocr=True)['urls']
    print(json.dumps({'mode':name,'psm':psm,'exact':len(set(found)&set(urls)),'expected':len(urls),'seconds':round(time.perf_counter()-t,2),'errors':[u for u in found if u not in urls]}),flush=True)
 finally:
  os.killpg(proc.pid,signal.SIGTERM);proc.wait(timeout=3)
