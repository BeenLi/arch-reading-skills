import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "_shared" / "scripts"))

from check_concept_length import EXAMPLE_LIMIT, OTHER_LIMIT, check, main, measure  # noqa: E402


def concept(example_body: int, other_body: int, *, mermaid_in_example: int = 0, mermaid_in_other: int = 0) -> str:
    """A concept note whose sections have known line counts.

    The example section is its heading plus ``example_body`` lines; the other
    sections are the title line plus ``other_body`` lines. Mermaid blocks of the
    given body size (plus two fence lines) are added on top and must not count.
    """
    def mermaid(n: int) -> list[str]:
        return ["```mermaid", *[f"    A{i} --> B{i}" for i in range(n)], "```"] if n else []

    lines = ["---", "type: concept", "aliases: [X]", "concept_type: mechanism", "---", "# X"]
    lines += [f"other {i}" for i in range(other_body)]
    lines += mermaid(mermaid_in_other)
    lines += ["## 直观例子"]
    lines += [f"example {i}" for i in range(example_body)]
    lines += mermaid(mermaid_in_example)
    return "\n".join(lines) + "\n"


class MeasureTest(unittest.TestCase):
    def test_counts_example_and_other_sections_without_frontmatter(self):
        self.assertEqual(measure(concept(20, 50)), (21, 51))

    def test_example_section_ends_at_the_next_h2_heading(self):
        text = concept(10, 30) + "## 核心要点\n" + "point\n" * 5
        self.assertEqual(measure(text), (11, 37))

    def test_mermaid_source_is_not_counted(self):
        text = concept(20, 50, mermaid_in_example=25, mermaid_in_other=15)
        self.assertEqual(measure(text), (21, 51))

    def test_image_embed_counts_as_one_line(self):
        text = concept(20, 50) + "![[00_assets/X_fig.png|示意图]]\n"
        self.assertEqual(measure(text), (22, 51))

    def test_other_fenced_code_is_counted(self):
        text = concept(20, 50) + "```python\nprint(1)\n```\n"
        self.assertEqual(measure(text), (24, 51))

    def test_missing_example_section_returns_none(self):
        self.assertIsNone(measure("---\ntype: concept\n---\n# X\n## 定义\n内容\n"))


class CheckTest(unittest.TestCase):
    def test_limits(self):
        self.assertEqual((EXAMPLE_LIMIT, OTHER_LIMIT), (100, 90))

    def test_sections_at_their_limits_pass(self):
        self.assertEqual(check(concept(EXAMPLE_LIMIT - 1, OTHER_LIMIT - 1)), [])

    def test_example_over_its_limit_is_reported(self):
        (problem,) = check(concept(EXAMPLE_LIMIT, 50))
        self.assertIn("直观例子", problem)
        self.assertIn(str(EXAMPLE_LIMIT + 1), problem)

    def test_other_sections_over_their_limit_are_reported(self):
        (problem,) = check(concept(20, OTHER_LIMIT))
        self.assertIn("其他段", problem)
        self.assertIn(str(OTHER_LIMIT + 1), problem)

    def test_long_mermaid_does_not_push_a_note_over(self):
        self.assertEqual(check(concept(60, 80, mermaid_in_example=40, mermaid_in_other=40)), [])

    def test_missing_example_section_is_reported(self):
        (problem,) = check("---\ntype: concept\n---\n# X\n## 定义\n内容\n")
        self.assertIn("直观例子", problem)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, *paths):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main([str(p) for p in paths])
        return code, out.getvalue(), err.getvalue()

    def test_exit_codes(self):
        good = self.dir / "good.md"
        good.write_text(concept(30, 60), encoding="utf-8")
        bad = self.dir / "bad.md"
        bad.write_text(concept(30, OTHER_LIMIT + 5), encoding="utf-8")

        code, out, _ = self.run_main(good)
        self.assertEqual(code, 0)
        self.assertIn(f"{good}: OK", out)

        code, out, _ = self.run_main(good, bad)
        self.assertEqual(code, 1)
        self.assertIn(f"{bad}:", out)

        code, _, err = self.run_main(self.dir / "missing.md")
        self.assertEqual(code, 2)
        self.assertIn("cannot read", err)


if __name__ == "__main__":
    unittest.main()
