#!/usr/bin/python3
"""Measure one frozen monitor frame; retain timings/hashes only, never screen text."""
import resource,hashlib,json,os,statistics,subprocess,tempfile,time
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from omalink import extract

out=Path(__file__).with_name('ocr-results.json')
report={'capture':{},'samples':[]}
monitors=json.loads(subprocess.check_output(['hyprctl','monitors','-j']))
m=next(m for m in monitors if m['focused'])
w=json.loads(subprocess.check_output(['hyprctl','activewindow','-j']))
report['monitor']={'width':m['width'],'height':m['height'],'scale':m['scale']}
with tempfile.TemporaryDirectory(prefix='omalink-bench-',dir=os.environ['XDG_RUNTIME_DIR']) as tmp:
    tmp=Path(tmp)
    for compression in [6,0]:
        timings=[]
        for _ in range(3):
            start=time.perf_counter()
            subprocess.run(['grim','-l',str(compression),'-o',m['name'],str(tmp/'monitor.png')],check=True)
            timings.append(time.perf_counter()-start)
        report['capture'][str(compression)]={'median_s':statistics.median(timings),'bytes':(tmp/'monitor.png').stat().st_size}
    # Crop from the SAME captured frame, not a changing window.
    x,y=w.get('at',[m['x'],m['y']]); width,height=w.get('size',[m['width'],m['height']])
    scale=m['scale']; geometry=f'{round(width*scale)}x{round(height*scale)}+{round((x-m["x"])*scale)}+{round((y-m["y"])*scale)}'
    subprocess.run(['magick',str(tmp/'monitor.png'),'-crop',geometry,'+repage',str(tmp/'window.png')],check=True)
    for scope in ['monitor','window']:
        for threads in [None,1,2,4]:
            times=[]; cpu=[]; counts=[]; hashes=[]
            for _ in range(3):
                env=os.environ.copy()
                if threads is None: env.pop('OMP_THREAD_LIMIT',None)
                else: env['OMP_THREAD_LIMIT']=str(threads)
                before=resource.getrusage(resource.RUSAGE_CHILDREN)
                start=time.perf_counter()
                r=subprocess.run(['tesseract',str(tmp/(scope+'.png')),'stdout','--oem','1','--psm','11','-l','eng','--dpi','150'],env=env,capture_output=True,text=True,check=True,timeout=45)
                times.append(time.perf_counter()-start)
                after=resource.getrusage(resource.RUSAGE_CHILDREN)
                cpu.append(after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime)
                urls=extract(r.stdout); counts.append(len(urls))
                hashes.append(hashlib.sha256(json.dumps(urls).encode()).hexdigest())
            row={'scope':scope,'threads':threads,'median_s':statistics.median(times),'cpu_s':statistics.median(cpu),'urls':counts,'result_hashes':hashes}
            report['samples'].append(row); out.write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps({k:v for k,v in row.items() if k!='result_hashes'}),flush=True)
print('Screenshots and OCR text discarded; measurements:',out)
