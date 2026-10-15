import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "paper-reader" / "scripts"))

from check_note_links import check, main  # noqa: E402

CLEAN_NOTE = """---
title: "X"
---

# 论文笔记：X

## 核心贡献

1. **前端**: 双模前端 ^contrib-1

## 动机实验与核心 Insights

### Insight 1：旧模型过时

证据见 [[#^fig1|Figure 1]] 与 [[#^tab1|Table I]]，对应 [[#^contrib-1|贡献1]]。

**设计启发**：→ [[#机制1：双模前端|机制1]]

## 系统设计总览

![[00_assets/X_fig1.png|Figure 1: Overview / 总览]] ^fig1

**Table I: Landscape**

| 项目 | 内容 |
|---|---|
| a | [[#机制1：双模前端\\|机制1]] 与 [[IPC]] |

^tab1

## 关键机制拆解

### 机制1：双模前端

`Figure 9` 只是代码；$$ 之外的 [[IPC]] 和 [[_concepts/metric/IPC|IPC]] 都能解析。

```mermaid
flowchart TB
    A["Figure 2 机制3"] --> B
```

$$
\\text{Table II} = 1
$$

> [!summary] X
> - **方法**: [[#机制1：双模前端|机制1]]
"""


class CheckNoteLinksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.root = root
        (root / "_concepts" / "metric").mkdir(parents=True)
        (root / "_concepts" / "metric" / "IPC.md").write_text("# IPC\n", encoding="utf-8")
        self.note_dir = root / "Arch" / "Eval"
        (self.note_dir / "00_assets").mkdir(parents=True)
        (self.note_dir / "00_assets" / "X_fig1.png").write_bytes(b"png")
        self.note = self.note_dir / "X.md"

    def tearDown(self):
        self.tmp.cleanup()

    def problems(self, text):
        return check(text, self.note, self.root)

    def messages(self, text):
        return [message for _, message in self.problems(text)]

    def test_clean_note_has_no_problems(self):
        self.assertEqual(self.problems(CLEAN_NOTE), [])

    def test_heading_link_must_match_a_heading_verbatim(self):
        text = CLEAN_NOTE + "\n见 [[#机制1：双模前端设计|机制1]]。\n"
        (problem,) = self.problems(text)
        self.assertEqual(problem[0], text.splitlines().index("见 [[#机制1：双模前端设计|机制1]]。") + 1)
        self.assertIn("机制1：双模前端设计", problem[1])

    def test_block_link_must_point_to_a_defined_anchor(self):
        (message,) = self.messages(CLEAN_NOTE + "\n见 [[#^fig7|Figure 7]]。\n")
        self.assertIn("^fig7", message)

    def test_duplicate_anchor_is_reported(self):
        (message,) = self.messages(CLEAN_NOTE + "\n另一段 ^fig1\n")
        self.assertIn("^fig1", message)

    def test_wikilink_must_resolve_to_a_note(self):
        (message,) = self.messages(CLEAN_NOTE + "\n见 [[Missing Concept]]。\n")
        self.assertIn("Missing Concept", message)

    def test_embed_must_resolve_to_a_file(self):
        (message,) = self.messages(CLEAN_NOTE + "\n![[00_assets/X_fig2.png|Figure 2: Missing]] ^fig2\n")
        self.assertIn("X_fig2.png", message)

    def test_bare_references_in_prose_are_reported(self):
        text = CLEAN_NOTE + "\n如 Figure 1 所示，Table I 和 机制1、Insight 1、贡献1 都没加链接。\n"
        messages = self.messages(text)
        for ref in ("Figure 1", "Table I", "机制1", "Insight 1", "贡献1"):
            self.assertTrue(any(ref in m for m in messages), (ref, messages))

    def test_bare_mechanism_and_contribution_with_a_space_are_reported(self):
        messages = self.messages(CLEAN_NOTE + "\n见 机制 1 和 贡献 2。\n")
        self.assertEqual(len(messages), 2, messages)
        self.assertIn("机制 1", messages[0])
        self.assertIn("贡献 2", messages[1])

    def test_bare_reference_directly_followed_by_chinese_is_reported(self):
        messages = self.messages(CLEAN_NOTE + "\n见 机制1和 贡献2–3的设计，以及 [[#^fig1|Figure 1]]–5的结果。\n")
        self.assertEqual(len(messages), 3, messages)
        for ref in ("机制1", "贡献2–3", "–5"):
            self.assertTrue(any(ref in m for m in messages), (ref, messages))

    def test_percentage_after_contribution_verb_is_not_reported(self):
        self.assertEqual(self.problems(CLEAN_NOTE + "\n分别贡献 39%/46%/58%，平均贡献61%。\n"), [])

    def test_bare_abbreviated_figure_is_reported(self):
        (message,) = self.messages(CLEAN_NOTE + "\n如 Fig. 3 所示。\n")
        self.assertIn("Fig. 3", message)

    def test_bare_range_or_list_is_reported_once_as_a_whole(self):
        for ref in ("Figure 3–5", "Figure 3-5", "Figure 3/5", "Figure 3~5", "Table IV/VI", "机制2–3"):
            with self.subTest(ref=ref):
                (message,) = self.messages(CLEAN_NOTE + f"\n见 {ref} 的结果。\n")
                self.assertIn(ref, message)

    def test_bare_continuation_after_a_linked_reference_is_reported(self):
        for line, tail in (("[[#^fig1|Figure 1]]–5", "–5"), ("[[#^tab1|Table I]]/II", "/II")):
            with self.subTest(line=line):
                (message,) = self.messages(CLEAN_NOTE + f"\n见 {line} 的结果。\n")
                self.assertIn(tail, message)

    def test_fully_linked_range_is_not_reported(self):
        text = CLEAN_NOTE + "\n见 [[#^fig1|Figure 1]]–[[#^fig1|5]] 与 [[#^tab1|Table I]]/[[#^tab1|II]]。\n"
        self.assertEqual(self.problems(text), [])

    def test_continuation_after_an_ordinary_link_is_not_reported(self):
        self.assertEqual(self.problems(CLEAN_NOTE + "\n[[IPC]]-4 与 [[IPC]]/2 都不是引用。\n"), [])

    def test_range_inside_code_math_or_image_alt_is_not_reported(self):
        text = CLEAN_NOTE + "\n`Figure 3–5`、$Table IV/VI$ 与 ![Figure 3-5](x.png) 都不是正文。\n"
        self.assertEqual(self.problems(text), [])

    def test_bare_reference_in_a_table_cell_is_reported(self):
        (message,) = self.messages(CLEAN_NOTE + "\n| 配置 | 见 Table IV |\n")
        self.assertIn("Table IV", message)

    def test_unescaped_alias_pipe_in_a_table_row_is_reported(self):
        (message,) = self.messages(CLEAN_NOTE + "\n| 改动 | [[#机制1：双模前端|机制1]] |\n")
        self.assertIn("\\|", message)

    def test_cli_exit_codes(self):
        self.note.write_text(CLEAN_NOTE, encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([str(self.note), "--root", str(self.root)]), 0)

        self.note.write_text(CLEAN_NOTE + "\n见 [[#^nope|x]]\n", encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([str(self.note), "--root", str(self.root)]), 1)
        self.assertIn(f"{self.note}:", out.getvalue())

        err = io.StringIO()
        with redirect_stderr(err):
            self.assertEqual(main([str(self.note_dir / "nope.md"), "--root", str(self.root)]), 2)
        self.assertIn("cannot read", err.getvalue())


if __name__ == "__main__":
    unittest.main()
