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


TREE = {"users/0/collections": [
    {"key": "A", "data": {"name": "Computer Architecture"}},
    {"key": "B", "data": {"name": "Memory & Storage", "parentCollection": "A"}},
    {"key": "C", "data": {"name": "Storage Systems", "parentCollection": "B"}},
    {"key": "D", "data": {"name": "Runtime & Systems", "parentCollection": "A"}},
    {"key": "E", "data": {"name": "Reading List"}},
]}


def test_leaf_tree_prints_hints_for_paths_below_the_root(capsys):
    zotero_add.leaf_tree(StubApi(TREE), "Computer Architecture",
                         {"Memory & Storage / Storage Systems": "SSD", "Runtime & Systems": "OS"})
    out = capsys.readouterr().out.splitlines()
    assert out == [
        "Computer Architecture",
        "  Memory & Storage",
        "    Storage Systems  key=C  -- SSD",
        "  Runtime & Systems  key=D  -- OS",
    ]


def test_leaf_tree_without_root_lists_every_top_level_collection(capsys):
    zotero_add.leaf_tree(StubApi(TREE), "", {"Reading List": "later"})
    out = capsys.readouterr().out
    assert "Computer Architecture\n" in out and "Reading List  key=E  -- later" in out


def test_leaf_tree_missing_root_stops_with_reason_and_fix(capsys):
    import pytest
    with pytest.raises(SystemExit) as stop:
        zotero_add.leaf_tree(StubApi(TREE), "Computer Architecture (typo)")
    message = str(stop.value.code)
    assert "没有名为 'Computer Architecture (typo)'" in message
    assert "Computer Architecture, Reading List" in message  # existing top-level collections
    assert "collection_root" in message and "user-config.json" in message
    assert capsys.readouterr().out == ""  # nothing listed to pick from


def test_default_config_ships_reference_taxonomy(monkeypatch, tmp_path):
    import user_config
    monkeypatch.setenv(user_config.CONFIG_ENV_VAR, str(tmp_path / "missing.json"))
    user_config.load_user_config.cache_clear()
    try:
        cfg = user_config.paper_to_zotero_config()
        assert cfg["collection_root"] == "Computer Architecture"
        assert len(cfg["collection_hints"]) == 18
        assert "Memory & Storage / Storage Systems" in cfg["collection_hints"]
    finally:
        user_config.load_user_config.cache_clear()
