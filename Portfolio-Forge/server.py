"""Portfolio Forge: local PBI server. Python 3.10+, no third-party packages."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data' / 'portfolio.json'
LOCK = threading.Lock()
STATUSES = ['Submitted', 'Triage', 'Refinement', 'Needs information', 'Ready', 'In progress', 'Blocked', 'Review', 'Done']
TYPES = ['Feature', 'Bug', 'Maintenance', 'Research']
AREAS = ['UI-CSS', 'UI-HTML', 'UI-JS', 'API-JS', 'API-CS', 'Database', 'Testing', 'Documentation', 'Infrastructure']
AGENTS = ['Unassigned', 'Portfolio Admin', 'Legacy Maintainer', 'UI Developer', 'API Developer', 'Database Developer', 'Tester', 'Product Strategist']


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return str(uuid.uuid4())


def initial():
    return {'schemaVersion': 1, 'projects': [{'id': uid(), 'name': 'Portfolio Forge', 'folder': ROOT.name}], 'pbis': []}


def save(state):
    DATA.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(state, indent=2, ensure_ascii=False) + '\n').encode()
    fd, name = tempfile.mkstemp(dir=DATA.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, DATA)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return payload


def read():
    if not DATA.exists():
        save(initial())
    payload = DATA.read_bytes()
    state = json.loads(payload)
    if not isinstance(state, dict) or state.get('schemaVersion') != 1:
        raise ValueError('Unsupported or invalid portfolio data; restore a backup')
    return state, payload


def tag(payload):
    return '"' + hashlib.sha256(payload).hexdigest() + '"'


def text_field(body, name, limit=20000, required=False):
    value = body.get(name, '')
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError(f'Invalid {name}')
    return value.strip()


def validate_pbi(pbi, state):
    if not any(p['id'] == pbi['projectId'] for p in state['projects']):
        raise ValueError('Unknown project')
    if pbi['type'] not in TYPES or pbi['status'] not in STATUSES or pbi['assignedAgent'] not in AGENTS:
        raise ValueError('Invalid type, status, or agent')
    if not isinstance(pbi['areas'], list) or any(a not in AREAS for a in pbi['areas']) or len(pbi['areas']) != len(set(pbi['areas'])):
        raise ValueError('Invalid work areas')
    deps = pbi['dependencies']
    if not isinstance(deps, list) or not all(isinstance(x, str) for x in deps) or len(deps) != len(set(deps)):
        raise ValueError('Invalid dependencies')
    if pbi['id'] in deps or any(not any(item['id'] == dep for item in state['pbis']) for dep in deps):
        raise ValueError('Dependencies must reference other existing PBIs')
    graph = {item['id']: item['dependencies'] for item in state['pbis']}
    graph[pbi['id']] = deps
    def visit(node, active, done):
        if node in active:
            raise ValueError('Dependencies cannot form a cycle')
        if node in done:
            return
        active.add(node)
        for child in graph.get(node, []):
            visit(child, active, done)
        active.remove(node)
        done.add(node)
    visit(pbi['id'], set(), set())
    if pbi['status'] in ['Ready', 'In progress', 'Review', 'Done']:
        if not pbi['acceptanceCriteria'] or not pbi['verificationPlan'] or pbi['assignedAgent'] == 'Unassigned':
            raise ValueError('Ready and later statuses require acceptance criteria, verification plan, and an assigned agent')
    if pbi['status'] == 'In progress' and any(next(x for x in state['pbis'] if x['id'] == dep)['status'] != 'Done' for dep in deps):
        raise ValueError('Complete dependencies before beginning work')
    if pbi['status'] == 'Done' and not pbi['result']:
        raise ValueError('Done requires a result with verification evidence')


class Handler(BaseHTTPRequestHandler):
    def allowed(self):
        hosts = {f'localhost:{self.server.server_port}', f'127.0.0.1:{self.server.server_port}'}
        origin = self.headers.get('Origin')
        if self.headers.get('Host') not in hosts or (origin and origin not in {'http://' + h for h in hosts}):
            self.error(403, 'Use localhost to access this server')
            return False
        return True

    def respond(self, status, payload, mime='application/json; charset=utf-8', etag=None):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if etag:
            self.send_header('ETag', etag)
        self.end_headers()
        self.wfile.write(payload)

    def error(self, status, message):
        self.respond(status, json.dumps({'error': message}).encode())

    def do_GET(self):
        if not self.allowed():
            return
        path = urlsplit(self.path).path
        try:
            if path == '/api/state':
                with LOCK:
                    _, payload = read()
                self.respond(200, payload, etag=tag(payload))
            elif path == '/api/meta':
                self.respond(200, json.dumps({'statuses': STATUSES, 'types': TYPES, 'areas': AREAS, 'agents': AGENTS, 'portfolioRoot': str(ROOT.parent)}).encode())
            elif path in ['/', '/index.html', '/app.js', '/styles.css']:
                name = 'index.html' if path == '/' else path[1:]
                mime = {'index.html': 'text/html; charset=utf-8', 'app.js': 'text/javascript; charset=utf-8', 'styles.css': 'text/css; charset=utf-8'}[name]
                self.respond(200, (ROOT / 'web' / name).read_bytes(), mime)
            else:
                self.error(404, 'Not found')
        except (OSError, ValueError):
            self.error(500, 'Cannot load portfolio; inspect the data file and server permissions')

    def mutate(self):
        if not self.allowed():
            return
        path = urlsplit(self.path).path
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            self.error(415, 'JSON required')
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 1024 * 1024:
                self.error(413, 'Request limit is 1 MB')
                return
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('Expected a JSON object')
            with LOCK:
                state, current = read()
                if self.headers.get('If-Match') != tag(current):
                    self.error(412, 'Portfolio changed. Refresh before saving; your draft is still in the form.')
                    return
                if path == '/api/projects' and self.command == 'POST':
                    name = text_field(body, 'name', 100, True)
                    folder = text_field(body, 'folder', 100, True)
                    if folder in ['.', '..'] or '/' in folder or '\\' in folder or ':' in folder:
                        raise ValueError('Folder must name one direct child of the portfolio parent')
                    target = (ROOT.parent / folder).resolve()
                    if target.parent != ROOT.parent.resolve() or not target.is_dir():
                        raise ValueError('Project folder must exist directly under the portfolio parent; escaping symlinks are not allowed')
                    if any(p['folder'].casefold() == folder.casefold() for p in state['projects']):
                        raise ValueError('Project folder is already registered')
                    state['projects'].append({'id': uid(), 'name': name, 'folder': folder})
                elif path == '/api/pbis' and self.command == 'POST':
                    item = {'id': uid(), 'number': max([p['number'] for p in state['pbis']], default=0) + 1,
                            'createdAt': now(), 'updatedAt': now(), 'comments': [], 'history': [],
                            'projectId': body.get('projectId'), 'type': body.get('type', 'Feature'),
                            'status': 'Submitted', 'assignedAgent': 'Unassigned', 'areas': [], 'dependencies': []}
                    for field in ['title', 'description', 'acceptanceCriteria', 'implementationPlan', 'verificationPlan', 'result']:
                        item[field] = text_field(body, field, 200 if field == 'title' else 20000, field in ['title', 'description'])
                    validate_pbi(item, state)
                    item['history'].append({'at': now(), 'actor': 'Owner', 'action': 'Created'})
                    state['pbis'].append(item)
                elif path.startswith('/api/pbis/'):
                    parts = path.strip('/').split('/')
                    if len(parts) not in [3, 4]:
                        self.error(404, 'Not found')
                        return
                    item = next((p for p in state['pbis'] if p['id'] == parts[2]), None)
                    if item is None:
                        self.error(404, 'PBI not found')
                        return
                    actor = text_field(body, 'actor', 100, True)
                    if actor not in ['Owner'] + AGENTS[1:]:
                        raise ValueError('Unknown actor')
                    if len(parts) == 4 and parts[3] == 'comments' and self.command == 'POST':
                        parent = body.get('parentMessageId')
                        if parent is not None and not any(c['id'] == parent for c in item['comments']):
                            raise ValueError('Reply must reference a comment on this PBI')
                        item['comments'].append({'id': uid(), 'author': actor, 'body': text_field(body, 'body', 20000, True), 'parentMessageId': parent, 'createdAt': now()})
                        action = 'Added comment'
                    elif len(parts) == 3 and self.command == 'PATCH':
                        old_status = item['status']
                        changed = []
                        for field in ['title', 'description', 'acceptanceCriteria', 'implementationPlan', 'verificationPlan', 'result']:
                            if field in body:
                                item[field] = text_field(body, field, 200 if field == 'title' else 20000, field in ['title', 'description'])
                                changed.append(field)
                        for field in ['projectId', 'type', 'status', 'assignedAgent', 'areas', 'dependencies']:
                            if field in body:
                                item[field] = body[field]
                                changed.append(field)
                        validate_pbi(item, state)
                        action = 'Updated ' + ', '.join(changed)
                        if old_status != item['status']:
                            action += f'; {old_status} → {item["status"]}'
                    else:
                        self.error(404, 'Not found')
                        return
                    item['updatedAt'] = now()
                    item['history'].append({'at': now(), 'actor': actor, 'action': action})
                else:
                    self.error(404, 'Not found')
                    return
                payload = save(state)
            self.respond(200, payload, etag=tag(payload))
        except (ValueError, TypeError, KeyError, UnicodeDecodeError) as error:
            self.error(400, str(error))
        except OSError:
            self.error(500, 'Cannot save portfolio data')

    do_POST = mutate
    do_PATCH = mutate


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    with LOCK:
        read()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Portfolio Forge: http://localhost:{args.port}\nData: {DATA}\nProject parent: {ROOT.parent}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
