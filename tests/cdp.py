"""F7.1 CDP driver, written for this card. Minimal, synchronous."""
import json, time, itertools, subprocess, os, socket, shutil, tempfile
import requests, websocket

CHROME = os.environ.get('CHROME_BIN') or os.path.expanduser(
    '~/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome')


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Browser:
    def __init__(self, port=None):
        self.port = port or free_port()
        self.profile = tempfile.mkdtemp(prefix='f71chrome-')
        self.proc = subprocess.Popen(
            [CHROME, '--headless=new', f'--remote-debugging-port={self.port}',
             f'--user-data-dir={self.profile}', '--no-sandbox',
             '--disable-gpu', '--hide-scrollbars',
             '--force-device-scale-factor=1', '--allow-file-access-from-files',
             '--disable-lcd-text', 'about:blank'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(200):
            try:
                requests.get(f'http://127.0.0.1:{self.port}/json/version',
                             timeout=0.5)
                return
            except Exception:
                time.sleep(0.1)
        raise RuntimeError('chrome did not come up')

    def stop(self):
        try:
            self.proc.terminate()
            self.proc.wait(10)
        except Exception:
            self.proc.kill()
        shutil.rmtree(self.profile, ignore_errors=True)


class Page:
    def __init__(self, browser, width=1280, height=900, reduced_motion=False):
        self.br = browser
        t = requests.put(
            f'http://127.0.0.1:{browser.port}/json/new?about:blank').json()
        self.tid = t['id']
        self.ws = websocket.create_connection(
            t['webSocketDebuggerUrl'], origin='', suppress_origin=True,
            timeout=60)
        self.ids = itertools.count(1)
        self.events = []
        self.send('Page.enable')
        self.send('Runtime.enable')
        self.send('Log.enable')
        self.resize(width, height)
        if reduced_motion:
            self.send('Emulation.setEmulatedMedia', features=[
                {'name': 'prefers-reduced-motion', 'value': 'reduce'}])

    def send(self, method, **params):
        mid = next(self.ids)
        self.ws.send(json.dumps({'id': mid, 'method': method,
                                 'params': params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get('id') == mid:
                if 'error' in msg:
                    raise RuntimeError(f'{method}: {msg["error"]}')
                return msg.get('result', {})
            self.events.append(msg)

    def resize(self, w, h=900):
        self.send('Emulation.setDeviceMetricsOverride', width=w, height=h,
                  deviceScaleFactor=1, mobile=False)

    def goto(self, url, settle=1.8):
        self.send('Page.navigate', url=url)
        time.sleep(settle)

    def ev(self, expr):
        r = self.send('Runtime.evaluate', expression=expr,
                      returnByValue=True, awaitPromise=True)
        if r.get('exceptionDetails'):
            raise RuntimeError(json.dumps(r['exceptionDetails'])[:600])
        return r['result'].get('value')

    def shot(self, path):
        d = self.send('Page.captureScreenshot', format='png',
                      captureBeyondViewport=False)
        import base64
        with open(path, 'wb') as f:
            f.write(base64.b64decode(d['data']))
        return path

    def console_problems(self):
        out = []
        for e in self.events:
            if e.get('method') == 'Log.entryAdded':
                en = e['params']['entry']
                if en.get('level') in ('error', 'warning'):
                    out.append(f"{en['level']}: {en.get('text','')[:200]}")
            if e.get('method') == 'Runtime.exceptionThrown':
                out.append('exception: ' + json.dumps(e['params'])[:200])
        return out

    def close(self):
        try:
            self.ws.close()
            requests.get(f'http://127.0.0.1:{self.br.port}/json/close/{self.tid}')
        except Exception:
            pass
