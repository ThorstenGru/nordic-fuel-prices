#!/usr/bin/env python3
"""EuroFuelPrices frontend test harness.

Serves the local web/ folder (no-store, so edits show up immediately) and answers the data requests the app makes
(<cc>.json, meta.json, health.json) from a disk cache of the LIVE site, so every test run sees the same snapshot.
Fault injection for stress tests (all via /__ctl):
    /__ctl?delay=1500            add latency to every data response (ms)
    /__ctl?bw=300                throttle data responses to ~300 kB/s
    /__ctl?fail=de,fr            answer HTTP 500 for those countries (use fail= to clear)
    /__ctl?flaky=0.3             randomly fail 30 % of data requests
    /__ctl?offline=1             refuse every data request (connection reset)
    /__ctl?reset=1               back to normal
/__log returns the request log, /__log?clear=1 empties it.

usage: harness.py <web_dir> <cache_dir> <port>          run the server
       harness.py <web_dir> <cache_dir> --prefetch      download every country file once, then exit
"""
import sys, os, re, time, json, random, threading, urllib.request, urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

WEB, CACHE = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
LIVE = 'https://eurofuelprices.com/'
DATA_RE = re.compile(r'^/([a-z]{2}|meta|health)\.json$')
CTL = {'delay': 0, 'bw': 0, 'fail': [], 'flaky': 0.0, 'offline': False}
LOG, LOCK = [], threading.Lock()
os.makedirs(CACHE, exist_ok=True)


def live(name, fresh=False):
    p = os.path.join(CACHE, name)
    if fresh or not os.path.exists(p):
        req = urllib.request.Request(LIVE + name, headers={'User-Agent': 'efp-test-harness'})
        with urllib.request.urlopen(req, timeout=90) as r:
            body = r.read()
        with open(p, 'wb') as f:
            f.write(body)
    with open(p, 'rb') as f:
        return f.read()


if len(sys.argv) > 3 and sys.argv[3] == '--prefetch':
    meta = json.loads(live('meta.json', fresh=True))
    live('health.json', fresh=True)
    total = 0
    for c in meta['countries']:
        name = c['country'].lower() + '.json'
        try:
            total += len(live(name, fresh=True))
            print('ok ', name)
        except Exception as e:
            print('ERR', name, e)
    print('prefetched', len(meta['countries']), 'countries,', round(total / 1e6, 1), 'MB raw; meta version', meta.get('version'))
    sys.exit(0)

PORT = int(sys.argv[3])


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=WEB, **k)

    def log_message(self, *a):
        pass

    def _send(self, code, body=b'', ctype='application/json'):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        if not self._hdr_cc:
            self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    _hdr_cc = False

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        t0 = time.time()
        if u.path == '/__ctl':
            if q.get('reset'):
                CTL.update({'delay': 0, 'bw': 0, 'fail': [], 'flaky': 0.0, 'offline': False})
            if 'delay' in q: CTL['delay'] = int(q['delay'])
            if 'bw' in q: CTL['bw'] = int(q['bw'])
            if 'fail' in q: CTL['fail'] = [x.strip().lower() for x in q['fail'].split(',') if x.strip()]
            if 'flaky' in q: CTL['flaky'] = float(q['flaky'])
            if 'offline' in q: CTL['offline'] = q['offline'] in ('1', 'true')
            return self._send(200, json.dumps(CTL).encode())
        if u.path == '/__log':
            with LOCK:
                out = json.dumps(LOG[-400:]).encode()
                if q.get('clear'): LOG.clear()
            return self._send(200, out)
        m = DATA_RE.match(u.path)
        if m:
            name = m.group(1)
            code, size = 200, 0
            try:
                if CTL['offline']:
                    self.connection.close(); code = 0
                    return
                if CTL['delay']: time.sleep(CTL['delay'] / 1000)
                if name in CTL['fail'] or (CTL['flaky'] and random.random() < CTL['flaky']):
                    code = 500
                    return self._send(500, b'{"error":"injected"}')
                body = live(name + '.json')
                size = len(body)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(size))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                if CTL['bw']:
                    chunk = max(1024, CTL['bw'] * 1024 // 10)
                    for i in range(0, size, chunk):
                        self.wfile.write(body[i:i + chunk]); self.wfile.flush(); time.sleep(0.1)
                else:
                    self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                code = -1
            except Exception as e:
                code = 599
                try: self._send(502, json.dumps({'error': str(e)}).encode())
                except Exception: pass
            finally:
                with LOCK:
                    LOG.append({'t': round(time.time(), 2), 'path': u.path, 'code': code, 'bytes': size, 'ms': int((time.time() - t0) * 1000)})
            return
        return super().do_GET()


class Srv(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


print(f'harness on http://localhost:{PORT}  web={WEB}  cache={CACHE}', flush=True)
Srv(('127.0.0.1', PORT), H).serve_forever()
