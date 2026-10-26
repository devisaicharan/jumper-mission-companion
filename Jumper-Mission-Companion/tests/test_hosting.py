"""Hosted session isolation, resource cleanup and request-boundary regressions."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from cloud_server import HostedApp
from mission.engine import KinematicBackend
from mission.hosting import HTTPError,SessionPool,origin,session_cookie
from tools.build_netlify import build


class HostedTests(unittest.TestCase):
    def setUp(self):
        self.app=HostedApp('preview',origins=['https://robot.example'],limit=2,start=False)
        self.addCleanup(self.app.close)

    def request(self,path='/api/config',method='GET',cookie='',token='',site=None,body=None,request_origin='https://robot.example',**extra):
        raw=json.dumps(body).encode() if body is not None else b''
        e=dict(REQUEST_METHOD=method,PATH_INFO=path,HTTP_COOKIE=cookie,HTTP_ORIGIN=request_origin,HTTP_X_MISSION_TOKEN=token,CONTENT_TYPE='application/json',CONTENT_LENGTH=str(len(raw)),**{'wsgi.input':io.BytesIO(raw)})
        if site:e['HTTP_SEC_FETCH_SITE']=site
        e.update(extra);received={}
        def respond(status,headers):received.update(status=int(status.split()[0]),headers=dict(headers))
        data=b''.join(self.app(e,respond));received['body']=json.loads(data) if received['headers']['Content-Type']=='application/json' else data
        return received

    def visitor(self):
        r=self.request();self.assertEqual(r['status'],200)
        return r['headers']['Set-Cookie'].split(';')[0],r['body']['token']

    def test_health_allocates_no_robot(self):
        r=self.request('/healthz');self.assertEqual(r['status'],200);self.assertEqual(len(self.app.pool.sessions),0)

    def test_distinct_cookies_tokens_and_secure_flags(self):
        a=self.request();b=self.request()
        self.assertNotEqual(a['body']['token'],b['body']['token'])
        self.assertNotEqual(a['headers']['Set-Cookie'],b['headers']['Set-Cookie'])
        for flag in ['HttpOnly','Secure','SameSite=Lax']:self.assertIn(flag,a['headers']['Set-Cookie'])
        self.assertNotIn('Access-Control-Allow-Origin',a['headers'])

    def test_motion_and_focus_are_isolated(self):
        ca,ta=self.visitor();cb,tb=self.visitor()
        self.assertEqual(self.request('/api/command','POST',ca,ta,body={'action':'wave'})['status'],200)
        a=self.request('/api/state',cookie=ca)['body'];b=self.request('/api/state',cookie=cb)['body']
        self.assertEqual(a['expression']['queued'],1);self.assertEqual(b['expression']['queued'],0)
        self.request('/api/command','POST',ca,ta,body={'action':'focus_start','payload':{'focus':12,'rest':6,'task':'Private task'}})
        b=self.request('/api/state',cookie=cb)['body'];self.assertEqual(b['focus']['state'],'idle');self.assertNotEqual(b['focus']['task'],'Private task')

    def test_another_session_token_cannot_control_robot(self):
        ca,ta=self.visitor();cb,tb=self.visitor()
        r=self.request('/api/command','POST',ca,tb,body={'action':'wave'});self.assertEqual(r['status'],403)
        self.assertEqual(self.request('/api/state',cookie=ca)['body']['expression']['queued'],0)

    def test_missing_cookie_cannot_read_or_control(self):
        self.assertEqual(self.request('/api/state')['status'],401)
        self.assertEqual(self.request('/api/command','POST',body={'action':'wave'})['status'],401)
        self.assertEqual(len(self.app.pool.sessions),0)

    def test_foreign_null_and_missing_origins_rejected(self):
        c,t=self.visitor()
        for value in ['https://evil.example','null','', 'https://robot.example.evil.com']:
            self.assertEqual(self.request('/api/command','POST',c,t,body={'action':'wave'},request_origin=value)['status'],403)

    def test_cross_site_config_cannot_allocate(self):
        self.assertEqual(self.request(site='cross-site')['status'],403);self.assertEqual(len(self.app.pool.sessions),0)

    def test_capacity_does_not_reuse_another_visitors_robot(self):
        c,t=self.visitor();self.visitor();r=self.request()
        self.assertEqual(r['status'],503);self.assertEqual(len(self.app.pool.sessions),2)
        self.assertEqual(self.request(cookie=c)['body']['token'],t)

    def test_cookie_fixation_not_adopted(self):
        supplied='a'*43;r=self.request(cookie='mission_session='+supplied)
        self.assertNotIn(supplied,r['headers']['Set-Cookie'])
        for malformed in ['mission_session=short','mission_session=../../secret','; bad=']:
            self.assertIsNone(session_cookie(malformed))

    def test_release_stops_only_own_session(self):
        ca,ta=self.visitor();cb,tb=self.visitor();old=self.app.pool.get(session_cookie(ca))
        r=self.request('/api/session/end','POST',ca,ta)
        self.assertEqual(r['status'],200);self.assertTrue(old.closed);self.assertIn('Max-Age=0',r['headers']['Set-Cookie'])
        self.assertEqual(self.request('/api/state',cookie=ca)['status'],401)
        self.assertEqual(self.request('/api/state',cookie=cb)['status'],200);self.visitor()

    def test_invalid_body_and_image_view_are_contained(self):
        c,t=self.visitor()
        for body in [[],{'action':'wave','payload':[]},{'action':123},{'action':'set_view','payload':{'mode':'image'}}]:
            self.assertEqual(self.request('/api/command','POST',c,t,body=body)['status'],400)
        self.assertEqual(self.request('/api/command','POST',c,t,CONTENT_LENGTH='32769')['status'],413)
        self.assertIsNone(self.request('/api/state',cookie=c)['body']['fault'])

    def test_command_rate_is_bounded(self):
        c,t=self.visitor();s=self.app.pool.get(session_cookie(c));s.budget=0;s.budget_at=s.clock()
        self.assertEqual(self.request('/api/command','POST',c,t,body={'action':'heartbeat'})['status'],429)

    def test_static_traversal_and_runtime_files_are_not_exposed(self):
        for path in ['/../server.py','/%2e%2e/server.py','/local-config.json','/.env','/_redirects']:
            self.assertEqual(self.request(path)['status'],404)
        self.assertEqual(self.request('/style.css')['status'],200)

    def test_idle_cleanup_retains_focus_but_caps_lifetime(self):
        now=[0.];pool=SessionPool(lambda maze:KinematicBackend(),'test',limit=1,idle=30,lifetime=120,clock=lambda:now[0],start=False)
        self.addCleanup(pool.close);s,_=pool.acquire(None);now[0]=31;pool.expire();self.assertTrue(s.closed)
        s,_=pool.acquire(None);s.command('focus_start',{'focus':100,'rest':5});now[0]=80;pool.expire();self.assertFalse(s.closed)
        now[0]=152;pool.expire();self.assertTrue(s.closed)

    def test_public_origins_require_exact_https(self):
        for value in ['*','null','https://a.example/path','https://a.example?x=1','https://u:p@a.example']:
            with self.assertRaises(ValueError):origin(value)
        with self.assertRaises(ValueError):HostedApp(origins=['http://a.example'],start=False)

    def test_native_start_failure_has_no_fake_fallback(self):
        def broken(maze):raise RuntimeError('test native load failure')
        app=HostedApp(factory=broken,origins=['https://robot.example'],start=False)
        self.addCleanup(app.close)
        with self.assertRaises(HTTPError) as caught:app.pool.acquire(None)
        self.assertEqual(caught.exception.status,503);self.assertEqual(len(app.pool.sessions),0)

    def test_netlify_build_requires_real_https_backend(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'site'
            for value in ['', 'http://localhost:10000','https://u:p@robot.example','https://robot.example/api']:
                with self.assertRaises(ValueError):build(value,target)
            build('https://robot.example/',target)
            self.assertEqual((target/'_redirects').read_text(),'/api/* https://robot.example/api/:splat 200\n')
            self.assertTrue((target/'index.html').is_file())
