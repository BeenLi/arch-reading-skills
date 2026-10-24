import importlib.util
import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "skills" / "_shared" / "user-config.json"
ORCHESTRATOR_SKILL = REPO_ROOT / "skills" / "daily-papers" / "SKILL.md"
FETCH_AND_SCORE = REPO_ROOT / "skills" / "daily-papers" / "scripts" / "fetch_and_score.py"


class DailyPapersThemeTests(unittest.TestCase):
    def test_config_is_architecture_first_with_llm_systems_second(self):
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        daily = config["daily_papers"]
        keywords = set(daily["keywords"])

        # 体系结构为主：多核、缓存 / 内存层次、异构计算、互连
        for keyword in ("multicore", "cache hierarchy", "memory hierarchy", "heterogeneous computing",
                        "cache coherence", "cxl", "interconnect", "accelerator architecture"):
            self.assertIn(keyword, keywords)
        # LLM 系统为辅，只保留核心词
        for keyword in ("llm serving", "llm inference", "kv cache"):
            self.assertIn(keyword, keywords)
        llm_terms = [k for k in keywords if "llm" in k or k in ("kv cache", "prefill", "mixture-of-experts")]
        self.assertLess(len(llm_terms), len(keywords) / 8)

        # 泛化的 ML 词不进加分表，否则 "neural network" / "training" 会给纯 ML 论文加分
        for generic in ("network", "serving", "inference", "training", "throughput"):
            self.assertNotIn(generic, daily["domain_boost_keywords"])
        self.assertIn("multicore", daily["focus_phrases"])
        self.assertEqual(daily["venue_rank_scores"], {"A": 3, "B": 2, "C": 1})

        for keyword in ("humanoid", "embodied ai", "vision-language action", "edge computing"):
            self.assertIn(keyword, daily["negative_keywords"])
        self.assertEqual(daily["top_n"], 20)

    def test_daily_papers_skill_states_theme_triage_and_defaults(self):
        text = ORCHESTRATOR_SKILL.read_text(encoding="utf-8")

        # 主题：体系结构为主、LLM 系统为辅；纯体系结构论文不因与 LLM 无关被排除
        for phrase in ("computer architecture researcher", "多核", "缓存层次与内存层次", "异构计算", "LLM 系统（辅）",
                       "与 LLM 无关的纯体系结构论文**不排除**", "CCF 等级"):
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


    def test_default_config_scores_architecture_and_llm_systems_titles(self):
        """默认配置来自作者 Zotero 里 Computer Architecture / LLM Infrastructure 两个分类。

        只给标题和 Zotero 里记录的 venue（arXiv / 无 venue 的不加 venue 分），也要过 min_score；
        真实抓取时会议论文带 venue、arXiv 论文带摘要，分数只会更高。
        """
        spec = importlib.util.spec_from_file_location("fetch_and_score_theme", FETCH_AND_SCORE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        def score(title, venue=""):
            return module.score_paper({"title": title, "abstract": "", "venue": venue, "source": ""})

        on_topic = [
            ("Demystifying CXL Memory with Genuine CXL-Ready Systems and Devices", "MICRO"),
            ("Characterizing Off-path SmartNIC for Accelerating Distributed Systems", "OSDI"),
            ("Accel-Sim: An Extensible Simulation Framework for Validated GPU Modeling", "ISCA"),
            ("Branch Prediction without the Full View of Global History", ""),
            ("LMCache: An Efficient KV Cache Layer for Enterprise-Scale LLM Inference", "arXiv"),
            ("ShadowServe: Interference-Free KV Cache Fetching for Distributed Prefix Caching", ""),
            ("Megatron-LM: Training Multi-Billion Parameter Language Models Using Model Parallelism", "arXiv"),
        ]
        for title, venue in on_topic:
            self.assertGreaterEqual(score(title, venue), module.MIN_SCORE, title)

        off_topic = [
            "Fault-Tolerant Offloading Framework for Real-Time Applications in Mobile Edge Computing",
            "Reliable Task Offloading in LEO Satellite Networks",
        ]
        for title in off_topic:
            self.assertEqual(score(title), -999, title)


if __name__ == "__main__":
    unittest.main()
