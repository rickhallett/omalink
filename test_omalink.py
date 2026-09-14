import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import omalink

class LinkTests(unittest.TestCase):
    def test_markdown_and_balanced_parentheses(self):
        self.assertEqual(omalink.extract('[Docs](https://example.com/docs). https://example.org/a_(b)'),
                         ['https://example.com/docs','https://example.org/a_(b)'])
    def test_dedup_and_query(self):
        self.assertEqual(omalink.extract('https://example.com/a?x=1&y=2 https://example.com/a?x=1&y=2'),['https://example.com/a?x=1&y=2'])
    def test_bare_domains_and_source_files(self):
        self.assertEqual(omalink.extract('github.com/rickhallett/omatag www.example.org app.py main.rs a@domain.com'),
                         ['https://github.com/rickhallett/omatag','https://www.example.org'])
    def test_scheme_spacing(self):
        self.assertEqual(omalink.extract('https: //example.com/path'),['https://example.com/path'])
    def test_truncated_urls(self):
        self.assertEqual(omalink.extract('https://example.com/… https://example.com/...'),[])
    def test_reject_dangerous_schemes_and_credentials(self):
        for url in ['javascript:alert(1)','file:///etc/passwd','--incognito','https://user:pass@example.com','https://example.com/\narg']:
            with self.subTest(url=url),self.assertRaises(ValueError): omalink.validate(url)
    def test_url_passed_as_single_argument(self):
        url='https://example.com/?q=$(touch-danger)&x=1'
        with patch.object(omalink.shutil,'which',return_value='/usr/bin/google-chrome-stable'):
            args=omalink.chrome_command(url)
        self.assertEqual(args[-2:],['--new-tab',url])
    def test_capture_path_ownership(self):
        with self.assertRaises(ValueError): omalink.owned('/tmp/unrelated.png')

class LocalImageTests(unittest.TestCase):
    def test_path_uri_and_dedup(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'sample.png'; p.write_bytes(b'fixture')
            self.assertEqual(omalink.extract(f'{p} {p.as_uri()}'),[p.as_uri()])
            with patch.object(omalink.shutil,'which',return_value='/usr/bin/google-chrome-stable'):
                self.assertEqual(omalink.chrome_command(p.as_uri())[-1],p.as_uri())
    def test_quoted_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'my image.png'; p.write_bytes(b'fixture')
            self.assertEqual(omalink.extract(f'"{p}"'),[p.as_uri()])
    def test_no_arbitrary_files_or_remote_file_hosts(self):
        for uri in ['file://server/path/image.png','file:///etc/passwd','/missing/image.png']:
            with self.subTest(uri=uri),self.assertRaises(ValueError): omalink.validate(uri)
    def test_image_marker_candidates_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(omalink,'RUNTIME',Path(tmp)):
            p=Path(tmp)/'capture-test.png'; p.write_bytes(b'capture')
            with patch.object(omalink,'run',return_value=SimpleNamespace(stdout='[Image #1]')), patch.object(omalink,'recent_images',return_value=['file:///sample.png']):
                result=omalink.ocr(p)
            self.assertEqual(result['urls'],['file:///sample.png'])
            self.assertIn('not resolved',result['note'])
            self.assertFalse(p.exists())

if __name__=='__main__': unittest.main()
