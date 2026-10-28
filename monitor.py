"""Local Claude usage counters and DeepSeek client. Never sends Claude transcripts."""
import json
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import subprocess

CST = timezone(timedelta(hours=8))
DATA = Path.home() / 'Library/Application Support/Dafeiyu'


def write_private(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
    os.chmod(temp, 0o600)
    temp.replace(path)


def api_key():
    """Reuse the existing official DeepSeek config without copying the secret."""
    base = Path.home() / 'Library/Application Support/Claude-3p/configLibrary'
    try:
        meta = json.loads((base / '_meta.json').read_text())
        ident = meta['appliedId']
        if '/' not in ident:
            d = json.loads((base / (ident + '.json')).read_text())
            if d.get('inferenceGatewayBaseUrl', '').rstrip('/') == 'https://api.deepseek.com/anthropic':
                if d.get('inferenceGatewayApiKey'):
                    return d['inferenceGatewayApiKey']
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        env = json.loads((Path.home() / '.claude/settings.json').read_text()).get('env', {})
        if env.get('ANTHROPIC_BASE_URL', '').rstrip('/') == 'https://api.deepseek.com/anthropic':
            return env.get('ANTHROPIC_AUTH_TOKEN') or env.get('ANTHROPIC_API_KEY') or ''
    except (OSError, ValueError, TypeError):
        pass
    return ''


def request_api(path, payload=None):
    key = api_key()
    if not key:
        raise RuntimeError('未找到 Claude 中的 DeepSeek Key')
    # Use macOS's TLS client and trust store. Secret headers travel over stdin,
    # never in command arguments, URLs or a temporary credential file.
    config = [
        'url = ' + json.dumps('https://api.deepseek.com/' + path),
        'header = ' + json.dumps('Authorization: Bearer ' + key),
        'header = "Content-Type: application/json"',
    ]
    if payload is not None:
        config.append('data = ' + json.dumps(json.dumps(payload,ensure_ascii=False),ensure_ascii=False))
    env = os.environ.copy()
    for k in ('DYLD_LIBRARY_PATH', 'DYLD_FALLBACK_LIBRARY_PATH'):
        env.pop(k,None)
    try:
        r = subprocess.run(['/usr/bin/curl','--config','-','--silent','--show-error',
            '--connect-timeout','8','--max-time','60','--write-out','\n%{http_code}'],
            input='\n'.join(config)+'\n', text=True, encoding='utf-8', capture_output=True,
            timeout=65, env=env)
        if r.returncode:
            write_private(DATA/'network-diagnostic.json', {'at':datetime.now(CST).isoformat(),
                'code':r.returncode,'detail':r.stderr.replace(key,'<redacted>')[:800]})
            raise RuntimeError('连接 DeepSeek 失败，请检查网络')
        body, status = r.stdout.rsplit('\n',1)
        if status != '200':
            raise RuntimeError('DeepSeek 返回 HTTP '+status)
        return json.loads(body)
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError('连接 DeepSeek 超时，请稍后重试') from None


def chat(messages):
    d = request_api('chat/completions', {
        'model': 'deepseek-flash',
        'messages': messages,
        'thinking': {'type': 'disabled'},
        'max_tokens': 250,
    })
    reply = d['choices'][0]['message']['content'].strip()
    return reply, d.get('usage', {})


def day(ts):
    try:
        return datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone(CST).date().isoformat()
    except (ValueError, AttributeError, TypeError):
        return ''


class UsageReader:
    """Incremental read; coalesces streamed blocks by session and message ID."""
    def __init__(self, root=None):
        self.root = Path(root) if root else Path.home() / '.claude/projects'
        self.files = {}

    def read(self, today=None):
        today = today or datetime.now(CST).date().isoformat()
        present = set()
        for p in self.root.rglob('*.jsonl'):
            if not p.is_file():
                continue
            present.add(p)
            try:
                st = p.stat()
                old = self.files.get(p)
                if old and old['stamp'] == (st.st_mtime_ns, st.st_size):
                    continue
                if not old or st.st_size < old['offset'] or st.st_ino != old['inode']:
                    old = {'offset': 0, 'inode': st.st_ino, 'records': {}, 'event': ('', '')}
                with p.open('rb') as f:
                    f.seek(old['offset'])
                    while True:
                        start = f.tell()
                        line = f.readline()
                        if not line:
                            break
                        if not line.endswith(b'\n'):
                            f.seek(start)
                            break
                        try:
                            d = json.loads(line)
                        except (ValueError, UnicodeDecodeError):
                            continue
                        typ = d.get('type')
                        ts = d.get('timestamp', '')
                        if typ in ('user', 'assistant') and ts >= old['event'][0]:
                            old['event'] = (ts, typ)
                        if typ != 'assistant':
                            continue
                        m = d.get('message') or {}
                        u = m.get('usage') or {}
                        if not u:
                            continue
                        mid = m.get('id') or d.get('requestId') or d.get('uuid')
                        key = str(d.get('sessionId', p.stem)) + ':' + str(mid)
                        rec = old['records'].setdefault(key, {'id':key, 'timestamp': ts, 'model': m.get('model', ''),
                            'input': 0, 'output': 0, 'cache': 0, 'creation': 0, 'project': Path(d.get('cwd') or '').name})
                        for dest, source in [('input', 'input_tokens'), ('output', 'output_tokens'),
                                             ('cache', 'cache_read_input_tokens'), ('creation', 'cache_creation_input_tokens')]:
                            rec[dest] = max(rec[dest], int(u.get(source) or 0))
                        rec['timestamp'] = max(rec['timestamp'], ts)
                    old['offset'] = f.tell()
                old['stamp'] = (st.st_mtime_ns, st.st_size)
                self.files[p] = old
            except (OSError, ValueError, TypeError):
                continue
        self.files = {p: v for p, v in self.files.items() if p in present}
        # A resumed or imported transcript can repeat an already billed message.
        unique = {}
        for value in self.files.values():
            for key, r in value['records'].items():
                if key not in unique:
                    unique[key] = dict(r)
                else:
                    for name in ('input','output','cache','creation'):
                        unique[key][name] = max(unique[key][name],r[name])
                    unique[key]['timestamp'] = max(unique[key]['timestamp'],r['timestamp'])
        records = list(unique.values())
        daily = [r for r in records if day(r['timestamp']) == today]
        last = max(records, key=lambda r: r['timestamp'], default=None)
        recent = max((v['event'] for v in self.files.values()), default=('', ''))
        return {'day': today, 'calls': len(daily), 'input': sum(r['input'] + r['cache'] + r['creation'] for r in daily),
                'output': sum(r['output'] for r in daily), 'cache': sum(r['cache'] for r in daily),
                'last': last, 'latest_event': recent, 'files': len(self.files)}


class BalanceLedger:
    """Observed account deductions only; never attributes other clients to Claude."""
    def __init__(self, path=None):
        self.path = Path(path) if path else DATA / 'balance-ledger.json'
        try:
            self.data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            self.data = {'days': {}}

    def update(self, response, now=None):
        now = now or datetime.now(CST)
        today = now.astimezone(CST).date().isoformat()
        out = []
        for info in response.get('balance_infos', []):
            currency = info['currency']
            balance = Decimal(info['total_balance'])
            ident = today + ':' + currency
            row = self.data['days'].setdefault(ident, {'last': str(balance), 'spent': '0', 'since': now.isoformat()})
            delta = Decimal(row['last']) - balance
            row['spent'] = str(Decimal(row['spent']) + max(Decimal(0), delta))
            row['last'] = str(balance)
            out.append({'currency': currency, 'balance': str(balance), 'spent': row['spent'], 'since': row['since']})
        self.data['updated'] = now.isoformat()
        write_private(self.path, self.data)
        return out
