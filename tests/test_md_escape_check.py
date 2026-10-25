import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "_shared" / "scripts"))

from md_escape_check import check, fix  # noqa: E402


class MdEscapeCheckTest(unittest.TestCase):
    def test_escapes_chained_array_index(self):
        self.assertEqual(fix("算一个 C[i][j] 要扫"), r"算一个 C\[i\]\[j\] 要扫")
        self.assertEqual(fix("| A[i][k] |"), r"| A\[i\]\[k\] |")

    def test_escapes_literal_dollars(self):
        self.assertEqual(fix("每页 $200，共 $800"), r"每页 \$200，共 \$800")

    def test_is_idempotent(self):
        once = fix("addr[42:39] and $HOME")
        self.assertEqual(fix(once), once)
        self.assertEqual(check(once), [])

    def test_leaves_code_math_and_links_alone(self):
        source = (
            "---\ntitle: x[0]\n---\n"
            "`C[i][j]` and ``a`b[0]`` and $x_i[k]$ and\n"
            "$$\nA[i] = \\$5\n$$\n"
            "```c\nsum[n] += w[n][i];\n```\n"
            "[[Loop Tiling]] ![[00_assets/a[1].png|fig]] [DOI](https://x.org/a[1])\n"
            "<!-- note[0] -->\n"
        )
        self.assertEqual(fix(source), source)
        self.assertEqual(check(source), [])

    def test_ignores_plain_brackets_and_real_links(self):
        source = "区间 [0, 1] 和 [text](url) 以及 [ref]"
        self.assertEqual(fix(source), source)

    def test_horizontal_rules_are_not_frontmatter(self):
        # regression: `---` separators in the body must not hide text between them
        source = "# T\n\n---\n\nB 在 C1 为 M[0]\n\n---\n"
        self.assertEqual([line for line, _ in check(source)], [5])

    def test_escapes_accidental_tags(self):
        self.assertEqual(fix("| #SMs | #Warps |"), r"| \#SMs | \#Warps |")
        self.assertEqual(fix("#include <x>"), r"\#include \<x\>")  # <x> is a placeholder, not HTML
        self.assertEqual(fix("ratio: #L3HitFraction / Clk"), r"ratio: \#L3HitFraction / Clk")

    def test_keeps_headings_numbers_and_non_tags(self):
        source = "# Title\n## Sub\n第 #1 名，C# 与 F#，issue #42\n"
        self.assertEqual(fix(source), source)

    def test_keeps_intentional_tags(self):
        source = "- [ ] 写周报 #t/2h ⏫\n- [ ] 复现 #t/halfday\n"
        self.assertEqual(fix(source), source)
        self.assertEqual(check(source), [])

    def test_check_reports_line_numbers(self):
        hits = check("ok\nE[est] ≈ T\n")
        self.assertEqual([line for line, _ in hits], [2])

    def test_keeps_obsidian_block_ids_and_in_note_links(self):
        source = (
            "![Figure 3: delta CDF](https://arxiv.org/html/x/x3.png) ^fig3\n\n"
            "| a | b |\n|---|---|\n| 1 | 2 |\n\n^tab1\n\n"
            "见 [[#^fig3|Figure 3]]、[[#^tab1|Table 1]] 与 [[#机制1：Change-based encoding|机制1]]。 ^eq-ttft\n"
            "1. **KV codec**: 三个观察 ^contrib-1\n\n"
            "| 机制 | 说明 |\n|---|---|\n| [[#机制1：X\\|机制1]] | 见 [[#^fig3\\|Figure 3]] |\n\n"
            "```mermaid\nflowchart TB\n  A --> B\n```\n\n^diag-arch\n"
        )
        self.assertEqual(fix(source), source)
        self.assertEqual(check(source), [])


class NewRulesTest(unittest.TestCase):
    def test_escapes_placeholders_but_keeps_html(self):
        self.assertEqual(fix("写到 <note-name>.md，类型 <T>"), r"写到 \<note-name\>.md，类型 \<T\>")
        self.assertEqual(fix("</Placeholder>"), r"\</Placeholder\>")
        source = "第一行<br>第二行 H<sub>2</sub>O <img src=\"a.png\"> <https://x.org> a < b"
        self.assertEqual(fix(source), source)

    def test_escapes_intraword_asterisks_only(self):
        self.assertEqual(fix("+7*MEM_LOAD 和 a*b*c"), r"+7\*MEM_LOAD 和 a\*b\*c")
        source = "**粗体** 和 *斜体* 以及 x * y 和 *.md"
        self.assertEqual(fix(source), source)

    def test_escapes_pipes_in_table_code_and_wikilinks(self):
        source = "| 命令 | 链接 |\n|---|---|\n| `ping <agent|all>` | [[Last Level Cache|LLC]] |\n"
        expected = "| 命令 | 链接 |\n|---|---|\n| `ping <agent\\|all>` | [[Last Level Cache\\|LLC]] |\n"
        self.assertEqual(fix(source), expected)
        self.assertEqual(len(check(source)), 2)

    def test_table_pipes_ignore_prose_and_fenced_code(self):
        source = "正文 `a|b` 和 [[X|y]]\n```\n| `a|b` |\n```\n"
        self.assertEqual(fix(source), source)

    def test_new_rules_are_idempotent(self):
        source = "| `a|b` | [[X|y]] |\n<T> 和 a*b\n"
        once = fix(source)
        self.assertEqual(fix(once), once)
        self.assertEqual(check(once), [])

    def test_nested_fences_stay_protected(self):
        # a ````markdown block that shows a ```mermaid block: all of it is code
        source = "````markdown\n```mermaid\nA[Start] -->|Yes| B\n```\n````\n"
        self.assertEqual(fix(source), source)
        self.assertEqual(fix(source + "C[i]\n"), source + "C\\[i\\]\n")

if __name__ == "__main__":
    unittest.main()
