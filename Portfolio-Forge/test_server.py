import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import server


class PortfolioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_root, self.original_data = server.ROOT, server.DATA
        server.ROOT = Path(self.temp.name) / 'portfolio-forge'
        server.ROOT.mkdir()
        server.DATA = server.ROOT / 'data' / 'portfolio.json'
        (server.ROOT.parent / 'Project-Alpha').mkdir()
        self.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.base = f'http://127.0.0.1:{self.http.server_port}'

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        server.ROOT, server.DATA = self.original_root, self.original_data
        self.temp.cleanup()

    def request(self, path='/api/state', method='GET', body=None, etag=None):
        headers = {'Content-Type': 'application/json'}
        if etag:
            headers['If-Match'] = etag
        request = urllib.request.Request(self.base + path, method=method, headers=headers,
                                         data=None if body is None else json.dumps(body).encode())
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.loads(response.read()), response.headers.get('ETag')
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read()), error.headers.get('ETag')

    def create(self):
        _, state, etag = self.request()
        code, state, etag = self.request('/api/pbis', 'POST', {'projectId': state['projects'][0]['id'], 'title': 'Remove underlines', 'description': 'Remove link underlines from navigation', 'type': 'Maintenance'}, etag)
        self.assertEqual(code, 200)
        return state['pbis'][-1], etag

    def test_persistence_conflict_and_readiness(self):
        item, etag = self.create()
        path = '/api/pbis/' + item['id']
        code, _, _ = self.request(path, 'PATCH', {'actor': 'Owner', 'status': 'Ready'}, etag)
        self.assertEqual(code, 400)
        code, state, newtag = self.request(path, 'PATCH', {'actor': 'Portfolio Admin', 'status': 'Ready', 'assignedAgent': 'UI Developer', 'areas': ['UI-CSS'], 'acceptanceCriteria': 'Navigation links have no underline', 'verificationPlan': 'Inspect default, hover and keyboard focus states'}, etag)
        self.assertEqual(code, 200)
        self.assertEqual(self.request(path, 'PATCH', {'actor': 'Owner', 'title': 'Stale'}, etag)[0], 412)
        self.assertEqual(json.loads(server.DATA.read_text())['pbis'][0]['status'], 'Ready')
        self.assertEqual(self.request(path, 'PATCH', {'actor': 'Owner', 'status': 'Done'}, newtag)[0], 400)

    def test_comments_and_cross_pbi_reply(self):
        item, etag = self.create()
        path = '/api/pbis/' + item['id'] + '/comments'
        code, state, etag = self.request(path, 'POST', {'actor': 'Owner', 'body': 'Include hover states'}, etag)
        self.assertEqual(code, 200)
        parent = state['pbis'][0]['comments'][0]['id']
        self.assertEqual(self.request(path, 'POST', {'actor': 'Fake Agent', 'body': 'Invalid'}, etag)[0], 400)
        code, _, _ = self.request(path, 'POST', {'actor': 'Portfolio Admin', 'body': 'Understood', 'parentMessageId': parent}, etag)
        self.assertEqual(code, 200)
        other, etag = self.create()
        self.assertEqual(self.request('/api/pbis/' + other['id'] + '/comments', 'POST', {'actor': 'Owner', 'body': 'Cross thread', 'parentMessageId': parent}, etag)[0], 400)

    def test_project_roots(self):
        _, _, etag = self.request()
        self.assertEqual(self.request('/api/projects', 'POST', {'name': 'Outside', 'folder': '../outside'}, etag)[0], 400)
        self.assertEqual(self.request('/api/projects', 'POST', {'name': 'Missing', 'folder': 'Missing'}, etag)[0], 400)
        self.assertEqual(self.request('/api/projects', 'POST', {'name': 'Alpha', 'folder': 'Project-Alpha'}, etag)[0], 200)

    def test_dependencies(self):
        first, _ = self.create()
        second, etag = self.create()
        code, _, etag = self.request('/api/pbis/' + first['id'], 'PATCH', {'actor': 'Owner', 'dependencies': [second['id']]}, etag)
        self.assertEqual(code, 200)
        self.assertEqual(self.request('/api/pbis/' + second['id'], 'PATCH', {'actor': 'Owner', 'dependencies': [first['id']]}, etag)[0], 400)
        self.assertEqual(self.request('/api/pbis/' + first['id'], 'PATCH', {'actor': 'Owner', 'status': 'In progress', 'assignedAgent': 'Legacy Maintainer', 'acceptanceCriteria': 'Complete task', 'verificationPlan': 'Verify task'}, etag)[0], 400)


if __name__ == '__main__':
    unittest.main()
