import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "skills" / "_shared" / "user-config.json"
ORCHESTRATOR_SKILL = REPO_ROOT / "skills" / "daily-papers" / "SKILL.md"


class DailyPapersThemeTests(unittest.TestCase):
    def test_config_uses_llm_arch_network_storage_theme(self):
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        daily = config["daily_papers"]

        keywords = set(daily["keywords"])
        boosts = set(daily["domain_boost_keywords"])
        negatives = set(daily["negative_keywords"])

        required_keywords = {
            "llm serving",
            "llm inference",
            "kv cache",
            "rdma",
            "interconnect",
            "memory hierarchy",
            "storage system",
            "accelerator architecture",
        }
        for keyword in required_keywords:
            self.assertIn(keyword, keywords)

        required_boosts = {
            "llm",
            "serving",
            "inference",
            "memory",
            "storage",
            "rdma",
            "interconnect",
            "accelerator",
        }
        for keyword in required_boosts:
            self.assertIn(keyword, boosts)

        required_negative_terms = {
            "humanoid",
            "whole-body control",
            "egocentric perception",
            "dexterous manipulation",
            "embodied ai",
            "vision-language action",
        }
        for keyword in required_negative_terms:
            self.assertIn(keyword, negatives)

        self.assertEqual(daily["top_n"], 20)

    def test_daily_papers_skill_states_theme_triage_and_defaults(self):
        text = ORCHESTRATOR_SKILL.read_text(encoding="utf-8")

        # 主题：只聚焦 LLM 的体系结构 / 网络通信 / 存储内存
        for phrase in ("LLM", "architecture", "network", "storage", "只聚焦"):
            self.assertIn(phrase, text)

        # 点评分流
        for phrase in (
            "主推（1-2 篇）",
            "备选（最多 3 篇）",
            "不要凑满 20 篇",
            "每篇只写 2 句",
            "没有 `has_hardware_eval` 的论文默认不进主推",
            "没有 `has_end_to_end_eval` 的 serving 论文只能做备选",
            "有 `has_real_workload` 的论文在同分情况下优先级更高",
        ):
            self.assertIn(phrase, text)

        # 默认只抓取 + 点评，精读由用户决定
        for phrase in ("默认只串联论文抓取和推荐生成两步", "是否精读交给用户决定", "默认不生成论文笔记"):
            self.assertIn(phrase, text)

    def test_notes_step_regenerates_skeleton_notes_and_checks_quality(self):
        text = ORCHESTRATOR_SKILL.read_text(encoding="utf-8")

        self.assertIn("行数 >= 100 且包含 `## 批判性思考`、`## 复现`、`## 关联笔记`、`## 速查卡片`", text)
        self.assertIn("**不包含**独立的 `## 关键公式` 或 `## 关键图表` section header", text)


if __name__ == "__main__":
    unittest.main()
