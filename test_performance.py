import json,os,subprocess,tempfile,time,unittest,uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import omalink,providers

class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.patches=[patch.object(omalink,'RUNTIME',self.root),patch.object(omalink,'config',return_value={'threads':1,'cache_ttl_s':30}),patch.object(omalink,'run',return_value=SimpleNamespace(stdout='https://example.org/a'))]
        for p in self.patches: p.start()
    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()
    def scan(self,content=b'pixels'):
        p=self.root/('capture-'+uuid.uuid4().hex+'.png'); p.write_bytes(content)
        result=omalink.ocr(p)
        self.assertFalse(p.exists())
        return result
    def test_unchanged_pixels_hit_changed_pixels_miss(self):
        self.assertEqual(self.scan()['source'],'window OCR')
        self.assertEqual(self.scan()['source'],'cached window OCR')
        self.assertEqual(self.scan(b'changed')['source'],'window OCR')
        self.assertEqual(omalink.run.call_count,2)
        self.assertEqual(omalink.run.call_args.kwargs['env']['OMP_THREAD_LIMIT'],'1')
    def test_expiry_and_disabled_cache(self):
        self.scan()
        entry=next((self.root/'cache').glob('*.json')); os.utime(entry,(0,0))
        self.assertEqual(self.scan()['source'],'window OCR')
        omalink.config.return_value['cache_ttl_s']=0
        self.scan(); self.scan()
        self.assertEqual(omalink.run.call_count,4)
    def test_corrupt_cache_falls_back(self):
        self.scan(); entry=next((self.root/'cache').glob('*.json')); entry.write_text('{"bad":true}')
        self.assertEqual(self.scan()['source'],'window OCR')
    def test_failed_ocr_deletes_capture(self):
        omalink.run.side_effect=subprocess.TimeoutExpired('tesseract',15)
        with self.assertRaises(subprocess.TimeoutExpired): self.scan()
        self.assertFalse(list(self.root.glob('capture-*.png')))
    def test_metrics_contain_no_url_or_text(self):
        self.scan()
        record=(self.root/'timings.jsonl').read_text()
        self.assertNotIn('example.org',record)
        self.assertEqual((self.root/'timings.jsonl').stat().st_mode & 0o777,0o600)

class GeometryTests(unittest.TestCase):
    def test_scaled_and_clipped(self):
        m={'width':3840,'height':2160,'scale':2,'x':-1920,'y':0}
        self.assertEqual(omalink.geometry({'at':[-2000,30],'size':[1000,1500]},m),'-1920,30 920x1050')
    def test_rotated_monitor(self):
        m={'width':1920,'height':1080,'scale':1,'x':0,'y':0,'transform':1}
        self.assertEqual(omalink.geometry({'at':[100,100],'size':[1400,1900]},m),'100,100 980x1820')
    def test_non_intersecting(self):
        with self.assertRaises(ValueError): omalink.geometry({'at':[5000,0],'size':[100,100]},{'width':1920,'height':1080,'x':0,'y':0})

class CaptureTests(unittest.TestCase):
    def test_window_and_monitor_grim_options_are_mutually_exclusive(self):
        monitor={'name':'test','focused':True,'width':1920,'height':1080,'x':0,'y':0,'scale':1}
        window={'pid':123,'class':'unknown','mapped':True,'at':[10,20],'size':[800,600]}
        def run(args,**kwargs):
            data=[monitor] if args[:2]==['hyprctl','monitors'] else window if args[:2]==['hyprctl','activewindow'] else {}
            return SimpleNamespace(stdout=json.dumps(data))
        with tempfile.TemporaryDirectory() as tmp,patch.object(omalink,'RUNTIME',Path(tmp)),patch.object(omalink,'run',side_effect=run) as mocked,patch.object(omalink,'config',return_value={'scope':'window','direct':False}):
            for scope in ['window','monitor']:
                mocked.reset_mock(); omalink.capture(scope)
                command=next(call.args[0] for call in mocked.call_args_list if call.args[0][0]=='grim')
                self.assertEqual('-g' in command,scope=='window')
                self.assertEqual('-o' in command,scope=='monitor')

class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.patch=patch.object(providers,'ROOT',self.root); self.patch.start()
        self.token=uuid.uuid4().hex; (self.root/self.token).mkdir()
        self.request={'at':time.time(),'pid':42,'provider':'foot','token':self.token}
        self.write_request()
    def write_request(self): (self.root/'direct-request.json').write_text(json.dumps(self.request))
    def tearDown(self): self.patch.stop(); self.tmp.cleanup()
    def test_correct_application_only(self):
        with patch.object(providers,'parents',return_value=[42]):
            self.assertTrue(providers.deliver({'text':'hello'},'foot'))
            self.assertFalse(providers.deliver({'text':'hello'},'chrome'))
        with patch.object(providers,'parents',return_value=[99]):
            self.assertFalse(providers.deliver({'text':'hello'},'foot'))
    def test_stale_or_late_response_ignored(self):
        self.request['at']-=5; self.write_request()
        with patch.object(providers,'parents',return_value=[42]):
            self.assertFalse(providers.deliver({'text':'hello'},'foot'))
            self.request['at']=time.time(); self.write_request(); (self.root/self.token).rmdir()
            self.assertFalse(providers.deliver({'text':'hello'},'foot'))
    def test_timeout_releases_key_and_cleans_up(self):
        token=uuid.uuid4().hex
        with patch.object(providers.subprocess,'run') as run:
            self.assertIsNone(providers.direct({'pid':42,'address':'0x123'},'foot',token,timeout=0))
        self.assertEqual(run.call_count,2)
        self.assertIn('state = "up"',run.call_args.args[0][-1])
        self.assertFalse((self.root/token).exists()); self.assertFalse((self.root/'direct-request.json').exists())
    def test_osc8_and_browser_href(self):
        data=omalink.collect('\x1b]8;;https://example.org/hidden\x1b\\label\x1b]8;;\x1b\\',['javascript:alert(1)','https://example.org/browser'])
        self.assertEqual(data['urls'],['https://example.org/hidden','https://example.org/browser'])

if __name__=='__main__': unittest.main()
