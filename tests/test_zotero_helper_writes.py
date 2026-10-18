import importlib.util
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
sys.path.insert(0, str(TESTS.parent / "skills" / "paper-reader" / "scripts"))

from test_zotero_local_api import FakeZotero, make_handler  # noqa: E402
from zotero_local_api import ZoteroLocalApi  # noqa: E402

SCRIPT = TESTS.parent / "skills" / "paper-reader" / "scripts" / "zotero_helper.py"


def load_helper():
    spec = importlib.util.spec_from_file_location("zotero_helper_writes_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ParsingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helper = load_helper()

    def test_field_assignments(self):
        self.assertEqual(
            self.helper.parse_field_assignments(["date=2012", "title=A = B"]),
            {"date": "2012", "title": "A = B"},
        )
        with self.assertRaises(ValueError):
            self.helper.parse_field_assignments(["date"])

    def test_creators_split_on_semicolons_last_word_is_the_last_name(self):
        self.assertEqual(
            self.helper.parse_creators("Gabriel H. Loh; Mike O'Connor; Plato"),
            [
                {"creatorType": "author", "firstName": "Gabriel H.", "lastName": "Loh"},
                {"creatorType": "author", "firstName": "Mike", "lastName": "O'Connor"},
                {"creatorType": "author", "firstName": "", "lastName": "Plato"},
            ],
        )

    def test_new_collection_list_keeps_order_and_ignores_duplicates(self):
        self.assertEqual(self.helper.new_collections(["A", "B"], add=["C", "A"], remove=["B"]), ["A", "C"])


class WriteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helper = load_helper()

    def setUp(self):
        self.state = FakeZotero()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.state))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.api = ZoteroLocalApi(base_url=f"http://127.0.0.1:{self.server.server_port}/api")

    def data(self):
        return self.state.items["ABCD1234"]["data"]

    def test_edit_preview_reports_changes_without_writing(self):
        result = self.helper.edit_item(self.api, "ABCD1234", {"title": "New", "date": ""}, apply=False)
        self.assertEqual(result["changes"], {"title": ("Old", "New")})
        self.assertFalse(result["applied"])
        self.assertEqual(self.state.patches, [])

    def test_edit_apply_writes_only_changed_fields(self):
        result = self.helper.edit_item(self.api, "ABCD1234", {"title": "New", "collections": ["COLA"]}, apply=True)
        self.assertTrue(result["applied"])
        self.assertEqual(self.state.patches, [{"title": "New"}])
        self.assertEqual(self.data()["title"], "New")

    def test_edit_with_nothing_to_change_does_not_ask_for_authorization(self):
        result = self.helper.edit_item(self.api, "ABCD1234", {"title": "Old"}, apply=True)
        self.assertFalse(result["applied"])
        self.assertEqual(self.state.authorizations, 0)

    def test_trash_marks_the_item_deleted(self):
        self.helper.trash_item(self.api, "ABCD1234", apply=True)
        self.assertEqual(self.data()["deleted"], 1)

    def test_change_collections_adds_and_removes(self):
        self.helper.change_collections(self.api, "ABCD1234", add=["COLB"], remove=["COLA"], apply=True)
        self.assertEqual(self.data()["collections"], ["COLB"])


if __name__ == "__main__":
    unittest.main()
