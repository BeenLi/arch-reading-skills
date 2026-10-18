import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "_shared" / "scripts"))

from backfill_venue_labels import main, relabel  # noqa: E402


def note(frontmatter: str, h1: str = "# 论文笔记：Accel-Sim: An Extensible Simulation Framework") -> str:
    return f"---\ntitle: \"X\"\n{frontmatter}\ncreated: 2026-10-14\n---\n\n{h1}\n\n## 元信息\n"


class RelabelTest(unittest.TestCase):
    def test_normalizes_venue_and_appends_label_to_h1(self):
        text, status = relabel(note('year: 2025\nvenue: "MICRO 2025"'))
        self.assertEqual(status, "updated")
        self.assertIn("\nvenue: MICRO\n", text)
        self.assertIn("\n# 论文笔记：Accel-Sim: An Extensible Simulation Framework (MICRO'25)\n", text)

    def test_is_idempotent(self):
        once, _ = relabel(note("year: 2020\nvenue: ISPASS"))
        twice, status = relabel(once)
        self.assertEqual(twice, once)
        self.assertEqual(status, "unchanged")

    def test_replaces_an_outdated_label(self):
        text, _ = relabel(note("year: 2025\nvenue: MICRO", h1="# 论文笔记：X (MICRO'24)"))
        self.assertIn("\n# 论文笔记：X (MICRO'25)\n", text)
        self.assertNotIn("MICRO'24", text)

    def test_keeps_parentheses_that_are_not_a_label(self):
        text, _ = relabel(note("year: 2024\nvenue: IEEE Access", h1="# 论文笔记：Foo (Bar)"))
        self.assertIn("\n# 论文笔记：Foo (Bar) (IEEE Access'24)\n", text)

    def test_adds_year_taken_from_the_venue_when_missing(self):
        text, _ = relabel(note('venue: "HOTI 2023"'))
        self.assertIn("\nvenue: HOTI\nyear: 2023\n", text)
        self.assertIn("(HOTI'23)", text)

    def test_unknown_venue_is_left_alone(self):
        original = note('year: 2024\nvenue: "Notes"')
        self.assertEqual(relabel(original), (original, "unknown"))

    def test_note_without_frontmatter_is_left_alone(self):
        self.assertEqual(relabel("# 论文笔记：X\n"), ("# 论文笔记：X\n", "no-frontmatter"))

    def test_only_the_first_h1_after_frontmatter_changes(self):
        text, _ = relabel(note("year: 2024\nvenue: ISCA") + "\n# 另一个一级标题\n")
        self.assertIn("\n# 另一个一级标题\n", text)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "PaperNotes"
        (self.root / "Topic").mkdir(parents=True)
        (self.root / "_concepts" / "hardware").mkdir(parents=True)
        self.paper = self.root / "Topic" / "Paper.md"
        self.paper.write_text(note("year: 2024\nvenue: SOSR"), encoding="utf-8")
        self.concept = self.root / "_concepts" / "hardware" / "TLB.md"
        self.concept.write_text(note("year: 2024\nvenue: ISCA"), encoding="utf-8")
        self.moc = self.root / "Topic" / "_index_Topic.md"
        self.moc.write_text(note("year: 2024\nvenue: ISCA"), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["--root", str(self.root), *argv])
        return code, out.getvalue()

    def test_dry_run_reports_without_writing(self):
        before = self.paper.read_text(encoding="utf-8")
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("SOSR'24", out)
        self.assertEqual(self.paper.read_text(encoding="utf-8"), before)

    def test_apply_writes_paper_notes_only(self):
        concept_before = self.concept.read_text(encoding="utf-8")
        moc_before = self.moc.read_text(encoding="utf-8")
        code, _ = self.run_main("--apply")
        self.assertEqual(code, 0)
        self.assertIn("(SOSR'24)", self.paper.read_text(encoding="utf-8"))
        self.assertEqual(self.concept.read_text(encoding="utf-8"), concept_before)
        self.assertEqual(self.moc.read_text(encoding="utf-8"), moc_before)


if __name__ == "__main__":
    unittest.main()
