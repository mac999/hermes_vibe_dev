import os
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys
sys.path.insert(0, BASE)

from app import app  # noqa: E402


class TestStellarDrift(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def test_index_serves_hud(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        for marker in ('<canvas id="space"', 'Sound', 'STELLAR DRIFT', 'spacecore.js',
                       'scene.js', 'audio.js', 'app.js', 'style.css'):
            self.assertIn(marker, html)

    def test_health(self):
        r = self.client.get('/api/health')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['status'], 'ok')
        self.assertEqual(r.get_json()['app'], 'stellar_drift')

    def test_static_assets(self):
        for path in ('/static/js/spacecore.js', '/static/js/scene.js',
                     '/static/js/audio.js', '/static/js/app.js',
                     '/static/css/style.css'):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, path)
            self.assertGreater(len(r.data), 200, path)

    def test_spacecore_is_umd(self):
        r = self.client.get('/static/js/spacecore.js')
        self.assertIn('module.exports = factory', r.get_data(as_text=True))
        self.assertIn('global.SpaceCore = factory', r.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
