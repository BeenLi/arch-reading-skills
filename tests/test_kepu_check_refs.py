import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "kepu-research-doc" / "scripts"))

from check_refs import check_md  # noqa: E402

GOOD = """# 主题

Primer（[参考 1](#ref-1)）给出两条不变量；CHI（[参考 2](#ref-2)）把它们写成网络协议。

| 方案 | 出处 |
|---|---|
| HSC | [参考 2](#ref-2) |

## 参考

1. <a id="ref-1"></a>V. Nagarajan 等. *A Primer on Memory Consistency and Cache Coherence*. 2020.
2. <a id="ref-2"></a>Arm. *AMBA CHI Architecture Specification*.
3. <a id="ref-3"></a>Arm. *CMN-700 TRM*.

> **数字口径说明**：128 个 HN-F 出自[参考 3](#ref-3)。
"""


class CheckRefsTests(unittest.TestCase):
    def test_clean_doc_passes(self):
        errors, notes = check_md(GOOD)
        self.assertEqual(errors, [])
        self.assertEqual(notes, [])

    def test_bare_citation_is_flagged(self):
        errors, _ = check_md(GOOD.replace("（[参考 1](#ref-1)）", "（参考 1）"))
        self.assertTrue(any("裸“参考 1”" in e for e in errors), errors)

    def test_link_to_missing_anchor_is_flagged(self):
        errors, _ = check_md(GOOD.replace("[参考 2](#ref-2)）把", "[参考 9](#ref-9)）把"))
        self.assertTrue(any("#ref-9" in e for e in errors), errors)

    def test_label_target_mismatch_is_flagged(self):
        errors, _ = check_md(GOOD.replace("[参考 1](#ref-1)", "[参考 1](#ref-2)"))
        self.assertTrue(any("对不上" in e for e in errors), errors)

    def test_missing_anchor_on_entry_is_flagged(self):
        errors, _ = check_md(GOOD.replace('3. <a id="ref-3"></a>', "3. "))
        self.assertTrue(errors)

    def test_uncited_entry_is_a_note_not_an_error(self):
        errors, notes = check_md(GOOD.replace("出自[参考 3](#ref-3)", "出自厂商手册"))
        self.assertEqual(errors, [])
        self.assertTrue(any("ref-3" in n for n in notes), notes)


if __name__ == "__main__":
    unittest.main()
