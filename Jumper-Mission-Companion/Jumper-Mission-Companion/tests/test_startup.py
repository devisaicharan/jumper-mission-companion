import io
import json
from pathlib import Path,PureWindowsPath
import sys
import tempfile
import unittest
import zipfile

import setup
from mission.native import bundle_file_key
from windows_start import run_child


class StartupTests(unittest.TestCase):
    def fake_download(self,url,destination,unsafe=False):
        prefix='jumper-'+setup.COMMIT
        with zipfile.ZipFile(destination,'w') as z:
            z.writestr(prefix+'/assets/jumper/jumper.xml','<mujoco/>')
            z.writestr(prefix+'/out/bundle_example/jumper/bundle.json','{}')
            if unsafe:z.writestr(prefix+'/../outside.txt','bad')
    def test_windows_controller_manifest_key(self):
        root=PureWindowsPath('D:/My Projects/jumper/bundle')
        file=root/'runtime/mjlab/win-amd64/controller.pyd'
        manifest={'runtime/mjlab/win-amd64/controller.pyd':{'sha256':'verified'}}
        self.assertNotIn(str(file.relative_to(root)),manifest)
        self.assertEqual(manifest[bundle_file_key(root,file)]['sha256'],'verified')
    def test_archive_setup_without_git(self):
        with tempfile.TemporaryDirectory() as t:
            destination=Path(t)/'Robot Assets'
            setup.install_source(destination,fetch=self.fake_download)
            setup.check_source(destination)
            self.assertEqual(json.loads((destination/'.mission-source.json').read_text())['commit'],setup.COMMIT)
    def test_unsafe_archive_never_installed(self):
        with tempfile.TemporaryDirectory() as t:
            destination=Path(t)/'robot'
            with self.assertRaises(RuntimeError):
                setup.install_source(destination,fetch=lambda u,p:self.fake_download(u,p,True))
            self.assertFalse(destination.exists())
            self.assertFalse((Path(t)/'outside.txt').exists())
    def test_failed_download_does_not_leave_partial_install(self):
        def fail(url,path):path.write_bytes(b'partial');raise OSError('interrupted download')
        with tempfile.TemporaryDirectory() as t:
            destination=Path(t)/'robot'
            with self.assertRaises(OSError):setup.install_source(destination,fetch=fail)
            self.assertFalse(destination.exists())
    def test_existing_unknown_folder_is_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'robot';root.mkdir();(root/'keep.txt').write_text('keep')
            with self.assertRaises(RuntimeError):setup.install_source(root,fetch=self.fake_download)
            self.assertEqual((root/'keep.txt').read_text(),'keep')
    def test_child_errors_are_written_to_log(self):
        log=io.StringIO()
        code=run_child([sys.executable,'-c',"import sys;print('clear setup error');sys.exit(7)"],log)
        self.assertEqual(code,7);self.assertIn('clear setup error',log.getvalue())


if __name__=='__main__':unittest.main()
