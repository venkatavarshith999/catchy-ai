import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import closing
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from backend import server
from backend.storage import initialize, connect
from llms.engine import analyze, baseline, redact

class EngineTests(unittest.TestCase):
    def test_credential_request_without_pressure(self):
        self.assertEqual(baseline(['Please read your OTP to me.'])['level'], 'high')
    def test_protective_language(self):
        self.assertEqual(baseline(['Never share your OTP or password.'])['score'], 0)
    def test_urgency_alone(self):
        self.assertLess(baseline(['Your hospital appointment is urgent.'])['score'], 30)
    def test_accumulation(self):
        texts=['This is your bank.','Your account is frozen, act right now.','Do not tell your family.','Tell me your verification code.']
        scores=[baseline(texts[:i])['score'] for i in range(1,5)]
        self.assertEqual(scores, sorted(scores))
        self.assertGreaterEqual(scores[-1],60)
        self.assertIn('secrecy',[s['key'] for s in baseline(texts)['signals']])
    def test_disclaimer_does_not_cancel_request(self):
        self.assertEqual(baseline(['Never share your OTP. But read the verification code to me.'])['level'],'high')
    def test_redaction(self):
        result=redact('OTP is 123456 and email hello@example.com phone +91 9876543210')
        self.assertNotIn('123456',result)
        self.assertNotIn('hello@example.com',result)
        self.assertNotIn('9876543210',result)
    def test_model_fallback(self):
        with patch.dict(os.environ,{'LLM_PROVIDER':'ollama'}), patch('urllib.request.urlopen',side_effect=OSError('unavailable')):
            result=analyze(['Read your OTP to me'])
        self.assertEqual(result['model_status'],'unavailable')
        self.assertEqual(result['level'],'high')
    def test_model_evidence_validation(self):
        output={'signals':[{'key':'credential','turn':1,'quote':'invented evidence not in transcript'}]}
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,*args): return json.dumps({'message':{'content':json.dumps(output)}}).encode()
        with patch.dict(os.environ,{'LLM_PROVIDER':'ollama'}),patch('urllib.request.urlopen',return_value=Response()):
            self.assertEqual(analyze(['Hello, good morning.'])['score'],0)

class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(dir=str(server.ROOT / "tests"))
        cls.env=patch.dict(os.environ,{'DATABASE_PATH':cls.temp.name+'/test.db','LLM_PROVIDER':'rules'})
        cls.env.start(); initialize()
        cls.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.http.daemon_threads=True
        cls.origin=f'http://127.0.0.1:{cls.http.server_port}'
        os.environ['APP_ORIGIN']=cls.origin
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.thread.join();cls.env.stop();cls.temp.cleanup()
    def setUp(self):
        server.LIMITS.clear();server.MEMORY.clear()
        with closing(connect()) as db:
            db.execute('DELETE FROM users');db.commit()
    def request(self,path,method='GET',data=None,cookie=None,origin=True):
        headers={'X-Catchy-Request':'1','Content-Type':'application/json'}
        if origin:headers['Origin']=self.origin
        if cookie:headers['Cookie']=cookie
        req=urllib.request.Request(self.origin+'/api'+path,data=json.dumps(data).encode() if data is not None else None,headers=headers,method=method)
        try:r=urllib.request.urlopen(req,timeout=10)
        except urllib.error.HTTPError as e:r=e
        with r:return r.status,json.loads(r.read()),r.headers
    def register(self,email='one@example.test'):
        code,data,headers=self.request('/auth/register','POST',{'name':'Test Person','email':email,'password':'test-password-123'})
        self.assertEqual(code,200,data)
        return headers['Set-Cookie'].split(';')[0]
    def call(self,cookie):
        code,data,_=self.request('/calls','POST',{'title':'Test call','mode':'manual','consent':True},cookie)
        self.assertEqual(code,201,data);return data['id']
    def test_health_and_static_security(self):
        self.assertEqual(self.request('/health')[0],200)
        with urllib.request.urlopen(self.origin) as r:
            self.assertIn('frame-ancestors',r.headers['Content-Security-Policy'])
            self.assertIn(b'catchy',r.read())
    def test_login_logout_and_password_hash(self):
        cookie=self.register()
        with closing(connect()) as db:
            self.assertNotIn('test-password-123',db.execute('SELECT password_hash FROM users').fetchone()[0])
        self.assertEqual(self.request('/me',cookie=cookie)[0],200)
        self.assertEqual(self.request('/auth/login','POST',{'email':'one@example.test','password':'wrong-password'})[0],401)
        self.assertEqual(self.request('/auth/login','POST',{'email':'one@example.test','password':'test-password-123'})[0],200)
        self.request('/auth/logout','POST',{},cookie)
        self.assertEqual(self.request('/me',cookie=cookie)[0],401)
    def test_cross_account_isolation(self):
        one=self.register();two=self.register('two@example.test');cid=self.call(one)
        self.assertEqual(self.request('/calls/'+cid,cookie=two)[0],404)
        self.assertEqual(self.request('/calls/'+cid,'DELETE',cookie=two)[0],404)
        self.assertEqual(self.request('/calls/'+cid+'/turns','POST',{'text':'Read OTP to me'},two)[0],404)
    def test_default_retention_and_finish(self):
        cookie=self.register();cid=self.call(cookie)
        code,result,_=self.request('/calls/'+cid+'/turns','POST',{'text':'Read your OTP to me'},cookie)
        self.assertEqual(code,200,result);self.assertEqual(result['level'],'high')
        data=self.request('/calls/'+cid,cookie=cookie)[1]
        self.assertEqual(data['turns'],[])
        self.request('/calls/'+cid+'/finish','POST',{},cookie)
        self.assertNotIn(cid,server.MEMORY)
        self.assertEqual(self.request('/calls/'+cid+'/turns','POST',{'text':'Hello'},cookie)[0],409)
    def test_opt_in_retention_and_delete(self):
        cookie=self.register()
        self.request('/settings','POST',{'retain_transcript':True,'spoken_warnings':False},cookie)
        cid=self.call(cookie)
        self.request('/calls/'+cid+'/turns','POST',{'text':'My OTP is 123456'},cookie)
        data=self.request('/calls/'+cid,cookie=cookie)[1]
        self.assertEqual(len(data['turns']),1);self.assertNotIn('123456',json.dumps(data))
        self.request('/calls/'+cid,'DELETE',cookie=cookie)
        self.assertEqual(self.request('/calls/'+cid,cookie=cookie)[0],404)
        with closing(connect()) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM turns').fetchone()[0],0)
    def test_origin_and_input_validation(self):
        self.assertEqual(self.request('/auth/register','POST',{},origin=False)[0],403)
        cookie=self.register()
        self.assertEqual(self.request('/calls','POST',{'title':'test','mode':'manual','consent':False},cookie)[0],422)
        self.assertEqual(self.request('/settings','POST',{'retain_transcript':'true','spoken_warnings':False},cookie)[0],422)
    def test_contacts_private_and_removable(self):
        one=self.register();two=self.register('two@example.test')
        data=self.request('/contacts','POST',{'name':'Family','phone':'+91 9000000000','relationship':'Family'},one)[1]
        cid=data['contacts'][0]['id']
        self.assertEqual(self.request('/contacts',cookie=two)[1]['contacts'],[])
        self.request('/contacts/'+cid,'DELETE',cookie=two)
        self.assertEqual(len(self.request('/contacts',cookie=one)[1]['contacts']),1)
        self.request('/contacts/'+cid,'DELETE',cookie=one)
        self.assertEqual(self.request('/contacts',cookie=one)[1]['contacts'],[])
    def test_missing_auth_and_body_limits(self):
        self.assertEqual(self.request('/calls')[0],401)
        cookie=self.register();cid=self.call(cookie)
        self.assertEqual(self.request('/calls/'+cid+'/turns','POST',{'text':'a'*1600},cookie)[0],422)
    def test_rate_limit(self):
        for _ in range(20):server.limited(('auth','127.0.0.1'),20,600)
        self.assertEqual(self.request('/auth/login','POST',{'email':'a@example.test','password':'password1234'})[0],429)

if __name__=='__main__':unittest.main()

