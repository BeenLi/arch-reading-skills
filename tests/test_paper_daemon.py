import importlib.util
import io
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "skills" / "paper-reader" / "scripts" / "paper_daemon.py"


def load_module():
    spec = importlib.util.spec_from_file_location("paper_daemon", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PaperDaemonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def _venue_db(self, tmp):
        db_path = Path(tmp) / "zotero.sqlite"
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE fields (fieldID INTEGER PRIMARY KEY, fieldName TEXT);
            CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT);
            CREATE TABLE itemData (itemID INTEGER, fieldID INTEGER, valueID INTEGER);
            INSERT INTO fields VALUES (1, 'conferenceName'), (2, 'date'), (3, 'repository');
            INSERT INTO itemDataValues VALUES
                (1, '2022 55th IEEE/ACM International Symposium on Microarchitecture (MICRO)'),
                (2, '2025-10-18'), (3, 'arXiv'), (4, '2024');
            INSERT INTO itemData VALUES (10, 1, 1), (10, 2, 2), (11, 3, 3), (11, 2, 4), (12, 2, 4);
            """
        )
        conn.commit()
        conn.close()
        return str(db_path)

    def test_get_venue_info_returns_short_name_and_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = self._venue_db(tmp)
            self.assertEqual(self.module.get_venue_info(db, 10), {"venue_short": "MICRO", "venue_label": "MICRO'25"})
            self.assertEqual(self.module.get_venue_info(db, 11), {"venue_short": "arXiv", "venue_label": "arXiv'24"})
            self.assertEqual(self.module.get_venue_info(db, 12), {})

    def test_get_venue_info_skips_a_truncated_conference_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "zotero.sqlite"
            conn = sqlite3.connect(db_path)
            conn.executescript(
                """
                CREATE TABLE fields (fieldID INTEGER PRIMARY KEY, fieldName TEXT);
                CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT);
                CREATE TABLE itemData (itemID INTEGER, fieldID INTEGER, valueID INTEGER);
                INSERT INTO fields VALUES (1, 'conferenceName'), (2, 'proceedingsTitle'), (3, 'date');
                INSERT INTO itemDataValues VALUES (1, 'the 30th annual international symposium'),
                    (2, 'Proceedings of the 30th annual international symposium on Computer architecture - ISCA ''03'), (3, '2003');
                INSERT INTO itemData VALUES (20, 1, 1), (20, 2, 2), (20, 3, 3);
                """
            )
            conn.commit()
            conn.close()
            self.assertEqual(self.module.get_venue_info(str(db_path), 20)["venue_label"], "ISCA'03")

    def _prompt_for(self, paper_source):
        captured = {}

        def fake_run(cmd, *args, **kwargs):
            captured["prompt"] = cmd[-1]
            raise self.module.subprocess.TimeoutExpired(cmd, 1)

        with patch.object(self.module.subprocess, "run", side_effect=fake_run):
            self.module.call_codex(paper_source, "Topic", 10)
        return captured["prompt"]

    def test_prompt_asks_for_the_venue_label_in_the_title(self):
        prompt = self._prompt_for({"title": "X", "pdf_path": "/x.pdf", "venue_short": "MICRO", "venue_label": "MICRO'25"})
        self.assertIn("(MICRO'25)", prompt)
        self.assertIn("venue: MICRO", prompt)

    def test_prompt_without_a_label_leaves_the_title_alone(self):
        prompt = self._prompt_for({"title": "X", "pdf_path": "/x.pdf"})
        self.assertNotIn("标题标签", prompt)

    def test_process_collection_cleans_temporary_zotero_db_on_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_db = Path(tmp) / "zotero_readonly_test.sqlite"
            temp_db.write_text("temporary db", encoding="utf-8")

            with (
                patch.object(self.module, "copy_zotero_db", return_value=str(temp_db)),
                patch.object(self.module, "get_collection_id_and_path", return_value=(1, "Research Topics")),
                patch.object(self.module, "get_papers_in_collection", side_effect=RuntimeError("boom")),
            ):
                with self.assertRaises(RuntimeError):
                    self.module.process_collection("Research Topics")

            self.assertFalse(temp_db.exists())

    def test_copy_zotero_db_sees_rows_still_in_uncheckpointed_wal(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "zotero.sqlite"
            writer = sqlite3.connect(db_path)
            try:
                writer.execute("PRAGMA journal_mode=WAL")
                writer.execute("CREATE TABLE items (itemID INTEGER PRIMARY KEY)")
                writer.commit()
                writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                writer.execute("PRAGMA wal_autocheckpoint=0")
                writer.execute("INSERT INTO items VALUES (4056)")
                writer.commit()
                self.assertTrue(Path(f"{db_path}-wal").exists())

                with patch.object(self.module, "ZOTERO_DB", str(db_path)):
                    snapshot = self.module.copy_zotero_db()
                try:
                    conn = sqlite3.connect(snapshot)
                    rows = conn.execute("SELECT itemID FROM items").fetchall()
                    conn.close()
                finally:
                    self.module.remove_snapshot(snapshot)
            finally:
                writer.close()

        self.assertEqual(rows, [(4056,)])

    def test_process_collection_cleans_snapshot_sidecars_on_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_db = Path(tmp) / "zotero_readonly_test.sqlite"
            copies = [temp_db, Path(f"{temp_db}-wal"), Path(f"{temp_db}-shm")]
            for path in copies:
                path.write_text("temporary db", encoding="utf-8")

            with (
                patch.object(self.module, "copy_zotero_db", return_value=str(temp_db)),
                patch.object(self.module, "get_collection_id_and_path", side_effect=RuntimeError("boom")),
            ):
                with self.assertRaises(RuntimeError):
                    self.module.process_collection("Research Topics")

            for path in copies:
                self.assertFalse(path.exists(), path)

    def test_list_command_removes_its_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_db = Path(tmp) / "zotero_readonly_test.sqlite"
            conn = sqlite3.connect(temp_db)
            conn.executescript(
                """
                CREATE TABLE collections (collectionID INTEGER PRIMARY KEY, collectionName TEXT);
                CREATE TABLE collectionItems (collectionID INTEGER, itemID INTEGER);
                INSERT INTO collections VALUES (1, 'Systems');
                INSERT INTO collectionItems VALUES (1, 100);
                """
            )
            conn.close()

            stdout = io.StringIO()
            with (
                patch.object(sys, "argv", ["paper_daemon.py", "--list"]),
                patch.object(self.module, "copy_zotero_db", return_value=str(temp_db)),
                redirect_stdout(stdout),
            ):
                self.module.main()

            self.assertIn("Systems: 1", stdout.getvalue())
            self.assertFalse(temp_db.exists())

    def test_process_collection_passes_planned_target_path_to_codex(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_db = Path(tmp) / "zotero_readonly_test.sqlite"
            temp_db.write_text("temporary db", encoding="utf-8")
            pdf_path = Path(tmp) / "paper.pdf"
            pdf_path.write_text("pdf", encoding="utf-8")
            paper_notes_root = Path(tmp) / "PaperNotes"
            captured = {}

            def fake_call_codex(*args):
                captured["args"] = args
                return True, ""

            with (
                patch.object(self.module, "PAPER_NOTES_ROOT", str(paper_notes_root)),
                patch.object(self.module, "copy_zotero_db", return_value=str(temp_db)),
                patch.object(self.module, "get_collection_id_and_path", return_value=(1, "Research Topics")),
                patch.object(
                    self.module,
                    "get_papers_in_collection",
                    return_value=[
                        {
                            "item_id": 100,
                            "title": "ASPLOS Paper",
                            "source_collection_path": "Venues/ASPLOS: Architectural Support",
                        }
                    ],
                ),
                patch.object(self.module, "load_progress", return_value={"completed": [], "failed": [], "current": None, "started_at": None}),
                patch.object(self.module, "save_progress"),
                patch.object(self.module, "get_paper_online_source", return_value={}),
                patch.object(self.module, "get_venue_info", return_value={}),
                patch.object(self.module, "get_pdf_path", return_value=str(pdf_path)),
                patch.object(self.module, "call_codex", side_effect=fake_call_codex),
            ):
                self.module.process_collection("Research Topics")

            self.assertEqual(len(captured["args"]), 4)
            save_plan = captured["args"][3]
            self.assertEqual(
                save_plan["target_path"],
                str(paper_notes_root / "Venues" / "ASPLOS_ Architectural Support" / "ASPLOS Paper.md"),
            )
            self.assertEqual(
                save_plan["frontmatter_updates"]["zotero_collection"],
                "Venues/ASPLOS_ Architectural Support",
            )

    def test_process_collection_skips_existing_note_by_zotero_item_id_even_when_filename_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_db = Path(tmp) / "zotero_readonly_test.sqlite"
            temp_db.write_text("temporary db", encoding="utf-8")
            paper_notes_root = Path(tmp) / "PaperNotes"
            existing = paper_notes_root / "_inbox" / "Old Saved Title.md"
            existing.parent.mkdir(parents=True)
            existing.write_text("---\nzotero_item_id: 100\ntitle: Old Saved Title\n---\n", encoding="utf-8")
            progress = {"completed": [], "failed": [], "current": None, "started_at": None}

            with (
                patch.object(self.module, "PAPER_NOTES_ROOT", str(paper_notes_root)),
                patch.object(self.module, "copy_zotero_db", return_value=str(temp_db)),
                patch.object(self.module, "get_collection_id_and_path", return_value=(1, "Research Topics")),
                patch.object(
                    self.module,
                    "get_papers_in_collection",
                    return_value=[
                        {
                            "item_id": 100,
                            "title": "Completely Different Zotero Title",
                            "source_collection_path": "Research Topics/LLM Infrastructure",
                        }
                    ],
                ),
                patch.object(self.module, "load_progress", return_value=progress),
                patch.object(self.module, "save_progress"),
                patch.object(self.module, "get_paper_online_source", return_value={}),
                patch.object(self.module, "get_venue_info", return_value={}),
                patch.object(self.module, "get_pdf_path", return_value=None),
                patch.object(self.module, "call_codex") as call_codex,
            ):
                self.module.process_collection("Research Topics")

        call_codex.assert_not_called()
        self.assertIn(100, progress["completed"])

    def test_process_collection_infers_method_name_for_save_path_from_title_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_db = Path(tmp) / "zotero_readonly_test.sqlite"
            temp_db.write_text("temporary db", encoding="utf-8")
            pdf_path = Path(tmp) / "paper.pdf"
            pdf_path.write_text("pdf", encoding="utf-8")
            paper_notes_root = Path(tmp) / "PaperNotes"
            captured = {}

            def fake_call_codex(*args):
                captured["args"] = args
                return True, ""

            with (
                patch.object(self.module, "PAPER_NOTES_ROOT", str(paper_notes_root)),
                patch.object(self.module, "copy_zotero_db", return_value=str(temp_db)),
                patch.object(self.module, "get_collection_id_and_path", return_value=(1, "Research Topics")),
                patch.object(
                    self.module,
                    "get_papers_in_collection",
                    return_value=[
                        {
                            "item_id": 100,
                            "title": "EBPC: Efficient Bufferless Packet Compression",
                            "source_collection_path": "Research Topics/Compression",
                        }
                    ],
                ),
                patch.object(self.module, "load_progress", return_value={"completed": [], "failed": [], "current": None, "started_at": None}),
                patch.object(self.module, "save_progress"),
                patch.object(self.module, "get_paper_online_source", return_value={"arxiv_id": "2501.01234", "doi": "10.1145/example"}),
                patch.object(self.module, "get_venue_info", return_value={}),
                patch.object(self.module, "get_pdf_path", return_value=str(pdf_path)),
                patch.object(self.module, "call_codex", side_effect=fake_call_codex),
            ):
                self.module.process_collection("Research Topics")

            save_plan = captured["args"][3]

        self.assertEqual(
            save_plan["target_path"],
            str(paper_notes_root / "Research Topics" / "Compression" / "EBPC.md"),
        )
        self.assertEqual(save_plan["frontmatter_updates"]["doi"], "10.1145/example")
        self.assertEqual(save_plan["frontmatter_updates"]["arxiv_id"], "2501.01234")


if __name__ == "__main__":
    unittest.main()
