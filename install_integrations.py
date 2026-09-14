#!/usr/bin/python3
"""Install optional direct text bridges while preserving existing settings."""
import json,os,shutil,time
from pathlib import Path
root=Path(__file__).resolve().parent
home=Path.home(); config=Path(os.environ.get('XDG_CONFIG_HOME',home/'.config'))
app=config/'omalink'; app.mkdir(parents=True,exist_ok=True)
stamp=str(int(time.time()))

def write_preserving(path,text):
    if path.exists(): shutil.copy2(path,path.with_name(path.name+'.bak-omalink-'+stamp))
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text)

settings=app/'config.json'
if not settings.exists(): settings.write_text(json.dumps({'scope':'window','threads':1,'cache_ttl_s':30,'direct':True},indent=2)+'\n')
foot=config/'foot/foot.ini'; text=foot.read_text()
pipe='pipe-visible=['+str(home/'.local/bin/omalink')+' from-stdin] Mod1+Shift+u'
if pipe not in text:
    if '[key-bindings]' not in text: text+='\n[key-bindings]\n'
    text=text.replace('[key-bindings]\n','[key-bindings]\n# omalink direct visible-text bridge (new terminal sessions).\n'+pipe+'\n')
    write_preserving(foot,text)
    (app/'foot-enabled-at').write_text(str(time.time()))
# A user desktop override enables Chrome's native accessibility bridge on the
# next ordinary launch. Keep the basename so Omarchy browser focusing works.
wrapper=home/'.local/share/omalink/bin/google-chrome-stable'
wrapper.parent.mkdir(parents=True,exist_ok=True)
wrapper.write_text('#!/bin/sh\nexport ACCESSIBILITY_ENABLED=1\nexec /usr/bin/google-chrome-stable --force-renderer-accessibility "$@"\n')
wrapper.chmod(0o755)
desktop=home/'.local/share/applications/google-chrome.desktop'
source=desktop if desktop.exists() else Path('/usr/share/applications/google-chrome.desktop')
original=source.read_text()
updated=original.replace('Exec=/usr/bin/google-chrome-stable','Exec='+str(wrapper))
# Normalize duplicate/action-only WMClass keys present in the packaged entry.
lines=[]; group=''; seen=False
for line in updated.splitlines():
    if line.startswith('['): group=line
    if line.startswith('StartupWMClass='):
        if group!='[Desktop Entry]' or seen: continue
        seen=True; line='StartupWMClass=google-chrome'
    lines.append(line)
updated='\n'.join(lines)+'\n'
if not desktop.exists() or desktop.read_text()!=updated: write_preserving(desktop,updated)
print('Foot visible-text pipe and Chrome accessibility launcher installed.')
print('Existing processes retain OCR fallback. New Foot and normal Chrome launches use direct text.')
