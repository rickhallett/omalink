#!/usr/bin/python3
"""OCR then reuse identical synthetic pixels; no user screen retained."""
import json,os,statistics,subprocess,sys,tempfile,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import omalink
with tempfile.TemporaryDirectory(prefix='omalink-cache-',dir=os.environ['XDG_RUNTIME_DIR']) as tmp,patch.object(omalink,'RUNTIME',Path(tmp)):
    original=Path(tmp)/'fixture.png'
    subprocess.run(['magick','-size','1701x1390','xc:#181818','-font',subprocess.check_output(['fc-match','-f','%{file}','monospace'],text=True),'-pointsize','24','-fill','#eeeeee','-annotate','+40+80','https://example.com/terminal','-annotate','+40+140','https://docs.python.org/3/',str(original)],check=True)
    values=[]
    for i in range(4):
        image=Path(tmp)/('capture-'+str(i)+'.png'); image.write_bytes(original.read_bytes())
        start=time.perf_counter(); result=omalink.ocr(image); elapsed=(time.perf_counter()-start)*1000
        assert set(result['urls'])=={'https://example.com/terminal','https://docs.python.org/3/'}
        values.append(elapsed)
    print(json.dumps({'fixture':'1701x1390 two URLs','cold_ms':values[0],'cached_samples_ms':values[1:],'cached_median_ms':statistics.median(values[1:])}))
