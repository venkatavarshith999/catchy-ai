"""Same-origin application server. Run behind an HTTPS reverse proxy when deployed."""
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from contextlib import closing
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from backend.storage import connect, initialize, ROOT
from llms.engine import analyze, redact

LIMITS = defaultdict(deque)
RATE_LOCK = threading.Lock()
CALL_LOCKS = [threading.Lock() for _ in range(64)]
MEMORY = {}  # Ephemeral, bounded conversation memory; never raw audio.
MEMORY_LOCK = threading.Lock()
TTL = 8 * 3600

def now():
    return datetime.now(timezone.utc).isoformat()

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 310000).hex()

def limited(key, count, window=60):
    with RATE_LOCK:
        stamp = time.monotonic()
        if len(LIMITS) > 10000:
            for stale in list(LIMITS):
                if not LIMITS[stale] or stamp - LIMITS[stale][-1] > 3600:
                    LIMITS.pop(stale, None)
        events = LIMITS[key]
        while events and events[0] < stamp - window:
            events.popleft()
        if len(events) >= count:
            return True
        events.append(stamp)
        return False

class APIError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message

class Handler(BaseHTTPRequestHandler):
    server_version = 'Catchy'

    def log_message(self, *_):
        pass  # Do not leak transcript, query strings, or credentials into logs.

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Permissions-Policy', 'microphone=(self), camera=(), geolocation=()')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'")
        super().end_headers()

    def reply(self, status, data, cookie=None):
        content = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(content)

    def user(self, db):
        jar = SimpleCookie()
        try:
            jar.load(self.headers.get('Cookie', ''))
            token = jar['catchy_session'].value
        except (KeyError, ValueError):
            raise APIError(401, 'Please sign in to continue.')
        row = db.execute('SELECT u.id,u.name,u.email FROM auth_sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?', (digest(token), time.time())).fetchone()
        if not row:
            raise APIError(401, 'Your session expired. Please sign in again.')
        return dict(row)

    def body(self):
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            raise APIError(415, 'Send application/json.')
        try:
            size = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            raise APIError(400, 'Invalid request length.')
        if not 0 < size <= 20000:
            raise APIError(413, 'Request too large or empty.')
        try:
            result = json.loads(self.rfile.read(size))
        except (ValueError, UnicodeError):
            raise APIError(400, 'Invalid JSON.')
        if not isinstance(result, dict):
            raise APIError(400, 'Expected a JSON object.')
        return result

    def text(self, data, key, low=1, high=200):
        value = data.get(key)
        if not isinstance(value, str) or not low <= len(value.strip()) <= high:
            raise APIError(422, f'{key} must contain {low}–{high} characters.')
        return value.strip()

    def do_GET(self):
        self.dispatch('GET')

    def do_POST(self):
        self.dispatch('POST')

    def do_DELETE(self):
        self.dispatch('DELETE')

    def dispatch(self, method):
        self.connection.settimeout(15)
        path = urlsplit(self.path).path
        try:
            if not path.startswith('/api/'):
                if method != 'GET':
                    raise APIError(405, 'Method not allowed.')
                return self.static(path)
            if method != 'GET':
                expected = os.environ.get('APP_ORIGIN', f'http://localhost:{self.server.server_port}')
                if self.headers.get('Origin') not in (expected,):
                    raise APIError(403, 'Origin rejected. Use the configured application URL.')
                if self.headers.get('X-Catchy-Request') != '1':
                    raise APIError(403, 'Missing request protection header.')
            if path == '/api/health' and method == 'GET':
                with closing(connect()) as db:
                    db.execute('SELECT 1').fetchone()
                return self.reply(200, {'status': 'ok', 'version': '1.0.0'})
            with closing(connect()) as db:
                result, status, cookie = self.route(db, method, path)
                db.commit()
            self.reply(status, result, cookie)
        except APIError as error:
            self.reply(error.status, {'error': error.message})
        except Exception:
            self.reply(500, {'error': 'The server could not complete this request. Please try again.'})

    def route(self, db, method, path):
        cookie = None
        if path in ('/api/auth/register', '/api/auth/login') and method == 'POST':
            if limited(('auth', self.client_address[0]), 20, 600):
                raise APIError(429, 'Too many attempts. Please wait a few minutes.')
            data = self.body()
            email = self.text(data, 'email', 5, 254).lower()
            password = self.text(data, 'password', 10, 128)
            if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
                raise APIError(422, 'Enter a valid email address.')
            if path.endswith('register'):
                name = self.text(data, 'name', 2, 80)
                if db.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone():
                    raise APIError(409, 'This email is already registered. Please sign in.')
                uid = secrets.token_hex(16)
                db.execute('INSERT INTO users VALUES (?,?,?,?,?)', (uid,name,email,password_hash(password),now()))
                db.execute('INSERT INTO settings(user_id) VALUES (?)', (uid,))
            else:
                row = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
                encoded = row['password_hash'] if row else password_hash('dummy-password')
                if not hmac.compare_digest(password_hash(password, encoded.split(':')[0]), encoded) or not row:
                    raise APIError(401, 'Email or password is incorrect.')
                uid, name = row['id'], row['name']
            token = secrets.token_urlsafe(32)
            db.execute('DELETE FROM auth_sessions WHERE expires_at<?', (time.time(),))
            db.execute('INSERT INTO auth_sessions VALUES (?,?,?)', (digest(token), uid, time.time()+TTL))
            secure = '; Secure' if os.environ.get('COOKIE_SECURE') == '1' else ''
            cookie = f'catchy_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={TTL}{secure}'
            return {'user': {'id': uid, 'name': name, 'email': email}}, 200, cookie
        user = self.user(db)
        uid = user['id']
        if limited(('api', uid), 180):
            raise APIError(429, 'Too many requests. Please wait a moment.')
        if path == '/api/me' and method == 'GET':
            return {'user': user, 'llm_provider': os.environ.get('LLM_PROVIDER','rules')}, 200, None
        if path == '/api/auth/logout' and method == 'POST':
            db.execute('DELETE FROM auth_sessions WHERE user_id=?', (uid,))
            return {'ok': True}, 200, 'catchy_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'
        if path == '/api/settings':
            if method == 'POST':
                data = self.body()
                if any(type(data.get(k)) is not bool for k in ['retain_transcript','spoken_warnings']):
                    raise APIError(422, 'Settings must be boolean values.')
                db.execute('UPDATE settings SET retain_transcript=?,spoken_warnings=? WHERE user_id=?', (data['retain_transcript'],data['spoken_warnings'],uid))
            elif method != 'GET':
                raise APIError(405, 'Method not allowed.')
            return dict(db.execute('SELECT retain_transcript,spoken_warnings FROM settings WHERE user_id=?',(uid,)).fetchone()), 200, None
        if path == '/api/contacts':
            if method == 'POST':
                data = self.body()
                name, phone, relationship = self.text(data,'name',2,80), self.text(data,'phone',7,25), self.text(data,'relationship',2,40)
                if not re.fullmatch(r'\+?[\d ()-]+', phone):
                    raise APIError(422, 'Enter a valid phone number.')
                if db.execute('SELECT COUNT(*) FROM contacts WHERE user_id=?',(uid,)).fetchone()[0] >= 5:
                    raise APIError(422,'You can save up to five trusted contacts.')
                db.execute('INSERT INTO contacts VALUES (?,?,?,?,?)',(secrets.token_hex(16),uid,name,phone,relationship))
            elif method != 'GET':
                raise APIError(405,'Method not allowed.')
            return {'contacts':[dict(r) for r in db.execute('SELECT id,name,phone,relationship FROM contacts WHERE user_id=?',(uid,))]}, 200, None
        if path.startswith('/api/contacts/') and method == 'DELETE':
            db.execute('DELETE FROM contacts WHERE id=? AND user_id=?',(path.split('/')[-1],uid))
            return {'ok':True},200,None
        if path == '/api/calls':
            if method == 'GET':
                return {'calls':[dict(r) for r in db.execute('SELECT * FROM calls WHERE user_id=? ORDER BY created_at DESC LIMIT 100',(uid,))]},200,None
            if method == 'POST':
                data = self.body()
                title = self.text(data,'title',1,100)
                mode = data.get('mode')
                if mode not in ['demo','manual','microphone'] or data.get('consent') is not True:
                    raise APIError(422,'Consent and a valid input mode are required.')
                cid, stamp = secrets.token_hex(16),now()
                retain = db.execute('SELECT retain_transcript FROM settings WHERE user_id=?',(uid,)).fetchone()[0]
                db.execute('INSERT INTO calls(id,user_id,title,mode,score,status,created_at,updated_at,retain_transcript) VALUES (?,?,?,?,?,?,?,?,?)',(cid,uid,title,mode,0,'active',stamp,stamp,retain))
                return {'id':cid,'retain_transcript':bool(retain)},201,None
        match = re.fullmatch(r'/api/calls/([a-f0-9]{32})(?:/(turns|finish))?',path)
        if match:
            cid, action = match.groups()
            row = db.execute('SELECT * FROM calls WHERE id=? AND user_id=?',(cid,uid)).fetchone()
            if not row:
                raise APIError(404,'Session not found.')
            if method == 'DELETE' and not action:
                with CALL_LOCKS[int(cid[:4],16) % len(CALL_LOCKS)]:
                    db.execute('DELETE FROM calls WHERE id=?',(cid,))
                    db.commit()
                    with MEMORY_LOCK:
                        MEMORY.pop(cid,None)
                return {'ok':True},200,None
            if method == 'GET' and not action:
                turns = [json.loads(r['analysis']) | {'text':r['text']} for r in db.execute('SELECT * FROM turns WHERE call_id=? ORDER BY position',(cid,))]
                return {'call':dict(row),'turns':turns},200,None
            if method == 'POST' and action == 'finish':
                with CALL_LOCKS[int(cid[:4],16) % len(CALL_LOCKS)]:
                    db.execute("UPDATE calls SET status='completed',updated_at=? WHERE id=?",(now(),cid))
                    db.commit()
                    with MEMORY_LOCK:
                        MEMORY.pop(cid,None)
                return {'ok':True},200,None
            if method == 'POST' and action == 'turns':
                data = self.body()
                text = self.text(data,'text',1,1500)
                with CALL_LOCKS[int(cid[:4],16) % len(CALL_LOCKS)]:
                    row = db.execute('SELECT * FROM calls WHERE id=? AND user_id=?',(cid,uid)).fetchone()
                    if not row or row['status'] != 'active':
                        raise APIError(409,'This session has ended. Start a new one.')
                    with MEMORY_LOCK:
                        stamp = time.monotonic()
                        for stale in list(MEMORY):
                            if stamp - MEMORY[stale][0] > 1800:
                                MEMORY.pop(stale,None)
                        if cid not in MEMORY and len(MEMORY) >= 500:
                            raise APIError(503,'Session capacity reached. Please try again later.')
                        prior = MEMORY.get(cid,(stamp,[]))[1]
                    if not prior and row['turn_count'] > 0:
                        if row['retain_transcript']:
                            prior = [r['text'] for r in db.execute('SELECT text FROM turns WHERE call_id=? ORDER BY position',(cid,))]
                        if not prior:
                            raise APIError(409,'Conversation memory expired. Start a new session.')
                    if len(prior) >= 60:
                        raise APIError(422,'Session limit reached. End this session and start a new one.')
                    turns = prior + [text]
                    started = time.perf_counter()
                    analysis = analyze(turns)
                    analysis['latency_ms'] = round((time.perf_counter()-started)*1000)
                    analysis['turn'] = len(turns)
                    with MEMORY_LOCK:
                        MEMORY[cid] = (time.monotonic(),turns)
                    db.execute('UPDATE calls SET score=?,updated_at=?,turn_count=? WHERE id=?',(analysis['score'],now(),len(turns),cid))
                    if row['retain_transcript']:
                        db.execute('INSERT INTO turns(call_id,position,text,analysis) VALUES (?,?,?,?)',(cid,len(turns),redact(text),json.dumps(analysis)))
                    db.commit()
                    return analysis,200,None
        raise APIError(404,'Endpoint not found.')

    def static(self, path):
        allowed = {'/':'index.html','/index.html':'index.html','/styles.css':'styles.css','/app.js':'app.js','/favicon.svg':'favicon.svg'}
        if path not in allowed:
            raise APIError(404,'Not found.')
        target = ROOT / 'frontend' / allowed[path]
        content = target.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', (mimetypes.guess_type(target.name)[0] or 'application/octet-stream') + '; charset=utf-8')
        self.send_header('Content-Length',str(len(content)))
        self.send_header('Cache-Control','no-cache')
        self.end_headers()
        self.wfile.write(content)

def cleanup_memory():
    while True:
        time.sleep(30)
        with MEMORY_LOCK:
            stamp = time.monotonic()
            for cid in list(MEMORY):
                if stamp - MEMORY[cid][0] > 1800:
                    MEMORY.pop(cid, None)

def main():
    initialize()
    threading.Thread(target=cleanup_memory, daemon=True).start()
    port = int(os.environ.get('PORT','8000'))
    host = os.environ.get('HOST','127.0.0.1')
    server = ThreadingHTTPServer((host,port),Handler)
    server.daemon_threads = True
    print(f'Catchy AI ready: http://localhost:{port}',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
