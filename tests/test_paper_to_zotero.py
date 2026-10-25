import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "paper-to-zotero" / "scripts" / "zotero_add.py"
spec = importlib.util.spec_from_file_location("zotero_add", SCRIPT)
zotero_add = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zotero_add)


class StubApi:
    """Answers the GET paths the duplicate check uses, without a running Zotero."""

    def __init__(self, responses):
        self.responses = responses

    def get(self, path):
        return self.responses[path.split("?")[0]]


def test_collection_paths_are_full_paths():
    api = StubApi({"users/0/collections": [
        {"key": "A", "data": {"name": "Computer Architecture"}},
        {"key": "B", "data": {"name": "Benchmarks", "parentCollection": "A"}},
        {"key": "C", "data": {"name": "Benchmark Suites", "parentCollection": "B"}},
    ]})
    assert zotero_add.collection_paths(api)["C"] == "Computer Architecture / Benchmarks / Benchmark Suites"


def test_pdf_paths_cover_stored_linked_and_absolute_files(monkeypatch, tmp_path):
    monkeypatch.setenv("ZOTERO_BASE_ATTACHMENT_PATH", str(tmp_path))
    api = StubApi({"users/0/items/P/children": [
        {"data": {"itemType": "attachment", "contentType": "application/pdf", "linkMode": "imported_file"},
         "links": {"enclosure": {"href": "file:///Users/me/Zotero/storage/K1/paper%20one.pdf"}}},
        {"data": {"itemType": "attachment", "contentType": "application/pdf", "linkMode": "linked_file",
                  "path": "attachments:Computer Architecture/paper two.pdf"}},
        {"data": {"itemType": "attachment", "contentType": "application/pdf", "linkMode": "linked_file",
                  "path": "/abs/paper three.pdf"}},
        {"data": {"itemType": "attachment", "contentType": "text/html", "linkMode": "imported_url"},
         "links": {"enclosure": {"href": "file:///Users/me/Zotero/storage/K4/page.html"}}},
        {"data": {"itemType": "note"}},
    ]})
    assert zotero_add.pdf_paths(api, "P") == [
        "/Users/me/Zotero/storage/K1/paper one.pdf",
        str(tmp_path / "Computer Architecture" / "paper two.pdf"),
        "/abs/paper three.pdf",
    ]
