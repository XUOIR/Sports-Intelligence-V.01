import io
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from research.nhl_history_fetch import acquire, NoRedirects


class Response(io.BytesIO):
    status = 200
    headers = {}


class Opener:
    def __init__(self, payload=None, error=None):
        self.payload = payload or {'data': [{'id': 1}], 'total': 1}
        self.error = error
        self.calls = 0

    def open(self, request, timeout):
        self.calls += 1
        if self.error:
            raise self.error
        return Response(json.dumps(self.payload).encode())


class FetchTests(unittest.TestCase):
    def test_success_is_cached_without_second_call_and_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            opener = Opener()
            payload, source = acquire(folder, 'game', {'limit': 2}, opener)
            self.assertEqual(payload['total'], 1)
            self.assertFalse(source['cache_hit'])
            self.assertTrue(acquire(folder, 'game', {'limit': 2}, opener)[1]['cache_hit'])
            self.assertEqual(opener.calls, 1)
            Path(source['path']).write_text('{}')
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                acquire(folder, 'game', {'limit': 2}, opener)

    def test_failures_remain_consumed_without_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            opener = Opener(error=OSError('network unavailable'))
            with self.assertRaises(OSError):
                acquire(folder, 'game', {}, opener)
            with self.assertRaisesRegex(ValueError, 'already attempted'):
                acquire(folder, 'game', {}, opener)
            self.assertEqual(opener.calls, 1)
            with closing(sqlite3.connect(Path(folder) / 'admission.sqlite3')) as conn:
                status, reserved = conn.execute('SELECT status,bytes FROM attempt').fetchone()
            self.assertEqual(status, 'FAILED')
            self.assertGreater(reserved, 0)

    def test_request_cap_applies_before_network(self):
        with tempfile.TemporaryDirectory() as folder, patch('research.nhl_history_fetch.MAX_ATTEMPTS', 1):
            opener = Opener()
            acquire(folder, 'game', {'limit': 1}, opener)
            with self.assertRaisesRegex(ValueError, 'budget exhausted'):
                acquire(folder, 'team', {}, opener)
            self.assertEqual(opener.calls, 1)

    def test_oversize_fails_closed_and_keeps_byte_reservation(self):
        with tempfile.TemporaryDirectory() as folder, patch('research.nhl_history_fetch.MAX_BYTES', 8):
            with self.assertRaisesRegex(ValueError, 'byte cap'):
                acquire(folder, 'game', {}, Opener())
            with closing(sqlite3.connect(Path(folder) / 'admission.sqlite3')) as conn:
                self.assertEqual(conn.execute('SELECT bytes FROM attempt').fetchone()[0], 8)

    def test_paid_or_unknown_routes_and_redirects_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                acquire(folder, 'https://api.the-odds-api.com/v4/sports', {}, Opener())
        with self.assertRaises(ValueError):
            NoRedirects().redirect_request(None, None, 302, '', {}, 'https://example.com')


if __name__ == '__main__':
    unittest.main()
