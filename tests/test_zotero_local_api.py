import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "paper-reader" / "scripts"))

from zotero_local_api import LocalApiError, VersionConflict, ZoteroLocalApi  # noqa: E402

SERVER_ID = "srv-123"


class FakeZotero:
    """Just enough of Zotero 10's local API to exercise the client's write path."""

    def __init__(self, *, remember=False, deny=False):
        self.remember = remember
        self.deny = deny
        self.items = {"ABCD1234": {"version": 5, "data": {"key": "ABCD1234", "title": "Old", "collections": ["COLA"]}}}
        self.keys: set[str] = set()
        self.authorizations = 0
        self.patches: list[dict] = []


def make_handler(state: FakeZotero):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, status, body=None, headers=None, text=None):
            self.send_response(status)
            self.send_header("Zotero-Server-ID", SERVER_ID)
            self.send_header("Content-Type", "text/plain" if text is not None else "application/json")
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            if text is not None:
                payload = text.encode()
            else:
                payload = json.dumps(body).encode() if body is not None else b""
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _body(self):
            length = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(length) or b"{}")

        def do_GET(self):
            if self.path == "/api/":
                return self._send(200, text="Nothing to see here.")  # what Zotero 10.0.6 really returns
            key = self.path.rsplit("/", 1)[-1]
            item = state.items.get(key)
            if not item:
                return self._send(404, {})
            return self._send(200, {"key": key, "version": item["version"], "data": item["data"]},
                              {"Last-Modified-Version": str(item["version"])})

        def do_POST(self):
            if self.path != "/api/local/authorize":
                return self._send(404, {})
            if self.headers.get("Zotero-Server-ID") != SERVER_ID:
                return self._send(428, {})
            state.authorizations += 1
            if state.deny:
                return self._send(403, {"denied": True})
            key = f"key{state.authorizations}"
            state.keys.add(key)
            return self._send(200, {"key": key, "remember": state.remember})

        def do_PATCH(self):
            if self.headers.get("Zotero-Server-ID") != SERVER_ID:
                return self._send(428, {})
            key = self.headers.get("Zotero-API-Key")
            if key not in state.keys:
                return self._send(401, {}, {"WWW-Authenticate": 'Zotero-API-Key realm="Zotero Local API"'})
            item_key = self.path.rsplit("/", 1)[-1]
            item = state.items[item_key]
            if self.headers.get("If-Unmodified-Since-Version") != str(item["version"]):
                return self._send(412, {})
            changes = self._body()
            state.patches.append(changes)
            item["data"].update(changes)
            item["version"] += 1
            if not state.remember:
                state.keys.discard(key)  # single-use key, consumed by a successful write
            return self._send(204)

    return Handler


class LocalApiTest(unittest.TestCase):
    def start(self, **kwargs):
        self.state = FakeZotero(**kwargs)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.state))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        return ZoteroLocalApi(base_url=f"http://127.0.0.1:{self.server.server_port}/api")

    def test_reads_server_id_and_item(self):
        api = self.start()
        self.assertEqual(api.server_id(), SERVER_ID)
        item = api.get_item("ABCD1234")
        self.assertEqual((item["version"], item["data"]["title"]), (5, "Old"))

    def test_update_authorizes_and_sends_the_version(self):
        api = self.start()
        api.update_item("ABCD1234", {"title": "New"})
        self.assertEqual(self.state.items["ABCD1234"]["data"]["title"], "New")
        self.assertEqual(self.state.patches, [{"title": "New"}])
        self.assertEqual(self.state.authorizations, 1)

    def test_single_use_key_is_requested_again_for_the_next_write(self):
        api = self.start()
        api.update_item("ABCD1234", {"title": "One"})
        api.update_item("ABCD1234", {"title": "Two"})
        self.assertEqual(self.state.authorizations, 2)
        self.assertEqual(self.state.items["ABCD1234"]["data"]["title"], "Two")

    def test_remembered_key_is_reused(self):
        api = self.start(remember=True)
        api.update_item("ABCD1234", {"title": "One"})
        api.update_item("ABCD1234", {"title": "Two"})
        self.assertEqual(self.state.authorizations, 1)

    def test_stale_version_raises_and_changes_nothing(self):
        api = self.start()
        with self.assertRaises(VersionConflict):
            api.update_item("ABCD1234", {"title": "New"}, version=4)
        self.assertEqual(self.state.items["ABCD1234"]["data"]["title"], "Old")

    def test_denied_authorization_raises(self):
        api = self.start(deny=True)
        with self.assertRaises(LocalApiError) as ctx:
            api.update_item("ABCD1234", {"title": "New"})
        self.assertIn("拒绝", str(ctx.exception))
        self.assertEqual(self.state.items["ABCD1234"]["data"]["title"], "Old")

    def test_unreachable_zotero_raises_a_clear_error(self):
        api = ZoteroLocalApi(base_url="http://127.0.0.1:9/api", timeout=1)
        with self.assertRaises(LocalApiError) as ctx:
            api.server_id()
        self.assertIn("Zotero", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
