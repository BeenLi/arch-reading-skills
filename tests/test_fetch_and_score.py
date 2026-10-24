import importlib.util
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "skills" / "daily-papers" / "scripts" / "fetch_and_score.py"
PROGRAM_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "program_pages"


def load_module():
    spec = importlib.util.spec_from_file_location("fetch_and_score", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FetchAndScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_score_paper_rewards_systems_relevance(self):
        paper = {
            "title": "A GPU Cluster Runtime for RDMA-Optimized LLM Serving",
            "abstract": (
                "We present a distributed systems runtime for LLM serving with "
                "RDMA-aware scheduling, collective communication optimization, "
                "and KV cache offloading across GPU clusters."
            ),
        }

        score = self.module.score_paper(paper)

        self.assertGreaterEqual(score, 4)

    def test_pure_agent_application_paper_scores_below_min_score(self):
        paper = {
            "title": "A Browser Agent for Automatic Web Shopping",
            "abstract": (
                "We build an LLM agent for browsing websites, completing forms, "
                "and executing shopping workflows with better success rate."
            ),
        }

        score = self.module.score_paper(paper)

        # agent 不再按名字一票否决（agent 也是 LLM 系统的 workload），没有体系结构内容就自然低于门槛
        self.assertGreaterEqual(score, 0)
        self.assertLess(score, self.module.MIN_SCORE)

    def test_score_paper_does_not_hard_exclude_negative_keyword_in_abstract_only(self):
        paper = {
            "title": "A GPU Cluster Runtime for RDMA-Optimized LLM Serving",
            "abstract": (
                "The evaluation compares against a browser agent workload while "
                "focusing on distributed inference, KV cache placement, and RDMA."
            ),
        }

        score = self.module.score_paper(paper)

        self.assertGreater(score, -999)

    def test_parse_dblp_proceedings_html_extracts_entries(self):
        html = """
        <html>
          <body>
            <ul class="publ-list">
              <li class="entry inproceedings">
                <span class="title">FlashInfer: Communication-Aware LLM Serving.</span>
                <span itemprop="author">Alice Smith</span>
                <span itemprop="author">Bob Lee</span>
                <nav class="publ">
                  <ul>
                    <li class="ee"><a href="https://doi.org/10.1145/example">DOI</a></li>
                  </ul>
                </nav>
              </li>
            </ul>
          </body>
        </html>
        """

        entries = self.module.parse_dblp_proceedings_html(html, venue="eurosys", year=2026)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "FlashInfer: Communication-Aware LLM Serving.")
        self.assertEqual(entries[0]["authors"], "Alice Smith, Bob Lee")
        self.assertEqual(entries[0]["source"], "dblp")
        self.assertEqual(entries[0]["venue"], "EuroSys 2026")

    def test_parse_dblp_proceedings_html_handles_realistic_cite_block(self):
        html = """
        <html><body>
        <ul class="publ-list">
          <li class="entry inproceedings">
            <cite>
              <span class="title" itemprop="name">Hardware-Accelerated Memory Disaggregation for LLM Serving</span>.
              <span itemprop="author"><a>Alice Smith</a></span>
              <span itemprop="author"><a>Bob Lee</a></span>
            </cite>
            <nav class="publ"><ul><li class="drop-down"><div><a href="https://doi.org/10.1145/test">doi</a></div></li></ul></nav>
          </li>
        </ul>
        </body></html>
        """

        entries = self.module.parse_dblp_proceedings_html(html, venue="ISCA", year=2025)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "Hardware-Accelerated Memory Disaggregation for LLM Serving.")

    def test_parse_dblp_proceedings_html_uses_venue_month_hint(self):
        html = """
        <html><body>
        <ul class="publ-list">
          <li class="entry inproceedings">
            <cite>
              <span class="title" itemprop="name">Fast GPU Cluster Scheduling for LLM Serving</span>.
            </cite>
          </li>
        </ul>
        </body></html>
        """

        entries = self.module.parse_dblp_proceedings_html(html, venue="MICRO", year=2026)

        self.assertEqual(entries[0]["date"], "2026-10-01")

    def test_parse_journal_html_does_not_apply_conference_month_hint(self):
        html = """
        <html><body>
        <ul class="publ-list">
          <li class="entry article">
            <cite>
              <span class="title" itemprop="name">Efficient Storage Systems for LLM Serving</span>.
            </cite>
          </li>
        </ul>
        </body></html>
        """

        entries = self.module.parse_journal_html(html, journal_name="IEEE TPDS", year=2026)

        self.assertEqual(entries[0]["date"], "2026-01-01")

    def test_extract_program_titles_skips_session_headers(self):
        html = """
        <html><body>
          <h2>Session 1A: LLM Serving: Throughput Optimization</h2>
          <h3>FlashServe: Fast and Elastic LLM Serving in GPU Clusters</h3>
        </body></html>
        """

        titles = self.module.extract_program_titles(html)

        self.assertEqual(titles, ["FlashServe: Fast and Elastic LLM Serving in GPU Clusters"])

    def test_paper_lookup_keys_returns_arxiv_doi_and_title(self):
        paper = {
            "url": "https://arxiv.org/abs/2501.01234",
            "title": "FlashInfer: Communication-Aware LLM Serving.",
            "doi": "10.1145/Example",
        }

        keys = self.module.paper_lookup_keys(paper)

        self.assertIn("arxiv:2501.01234", keys)
        self.assertIn("doi:10.1145/example", keys)
        self.assertIn("title:flashinfercommunicationawarellmserving", keys)

    def test_dblp_paper_with_doi_url_emits_doi_key(self):
        paper = {
            "url": "https://doi.org/10.1109/HPCA68181.2026.11408444",
            "title": "Oaken: Fast and Efficient LLM Serving.",
        }

        keys = self.module.paper_lookup_keys(paper)

        self.assertIn("doi:10.1109/hpca68181.2026.11408444", keys)
        self.assertIn("title:oakenfastandefficientllmserving", keys)
        self.assertFalse(any(k.startswith("arxiv:") for k in keys))

    def test_history_dedup_skips_dblp_paper_whose_title_is_in_history(self):
        history = [
            {"id": "Oaken: Fast and Efficient LLM Serving.", "title": "Oaken: Fast and Efficient LLM Serving.", "date": "2026-04-14"},
            {"id": "10.1109/HPCA68181.2026.11408444", "title": "Some HPCA Paper.", "date": "2026-04-14"},
        ]
        history_keys, _ = self.module.build_history_index(history)

        new_dblp_paper = {
            "source": "dblp",
            "url": "https://dblp.org/...",
            "title": "Oaken: Fast and Efficient LLM Serving.",
            "score": 10,
        }

        self.assertTrue(self.module.paper_lookup_keys(new_dblp_paper) & history_keys)

    def test_history_dedup_skips_paper_recorded_by_doi(self):
        history = [
            {"id": "10.1109/HPCA68181.2026.11408444", "title": "Some HPCA Paper.", "date": "2026-04-14"},
        ]
        history_keys, _ = self.module.build_history_index(history)

        new_paper = {
            "source": "dblp",
            "url": "https://doi.org/10.1109/HPCA68181.2026.11408444",
            "title": "Some HPCA Paper.",
            "score": 8,
        }

        self.assertTrue(self.module.paper_lookup_keys(new_paper) & history_keys)

    def test_apply_age_decay_reduces_score_for_year_old_papers(self):
        target = date(2026, 5, 14)
        papers = [
            {"date": "2026-05-13", "score": 10},  # 1 day, no decay
            {"date": "2025-12-01", "score": 10},  # ~165 days, 0.75 → 7
            {"date": "2025-01-01", "score": 10},  # ~500 days, 0.35 → 3
        ]

        self.module.apply_age_decay(papers, target)

        self.assertEqual(papers[0]["score"], 10)
        self.assertEqual(papers[1]["score"], 7)
        self.assertEqual(papers[2]["score"], 3)

    def test_select_with_quota_caps_dblp_share(self):
        candidates = (
            [{"source": "dblp", "score": 20 - i, "title": f"d{i}"} for i in range(15)]
            + [{"source": "arxiv", "score": 5 - (i % 3), "title": f"a{i}"} for i in range(10)]
        )

        top = self.module.select_with_quota(candidates, top_n=10, dblp_max_ratio=0.4)

        dblp_count = sum(1 for p in top if p["source"] == "dblp")
        self.assertLessEqual(dblp_count, 4)
        self.assertEqual(len(top), 10)

    def test_fetch_url_retries_transient_rate_limit(self):
        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"<feed />"

        attempts = []

        def fake_urlopen(req, timeout):
            attempts.append(req.full_url)
            if len(attempts) == 1:
                raise HTTPError(
                    req.full_url,
                    429,
                    "Too Many Requests",
                    {"Retry-After": "0"},
                    None,
                )
            return FakeResponse()

        with patch.object(self.module, "urlopen", side_effect=fake_urlopen), patch("time.sleep") as sleep:
            body = self.module.fetch_url("https://export.arxiv.org/api/query", timeout=1)

        self.assertEqual(body, "<feed />")
        self.assertEqual(len(attempts), 2)
        sleep.assert_called_once_with(0)


class ProgramPageTests(unittest.TestCase):
    """程序页解析：fixtures 是从真实页面截下来的片段（2026-10-24 抓取），测试不联网。"""

    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def parse_fixture(self, name):
        return self.module.parse_program_page((PROGRAM_FIXTURES / name).read_text(encoding="utf-8"))

    def test_paper_div_template_isca(self):
        entries = self.parse_fixture("isca2026.html")

        self.assertEqual(len(entries), 4)
        title, authors = entries[0]
        self.assertEqual(title, "MLX: Multi-Layer Execution for Structured LLM Workload Acceleration on Spatial Architectures")
        self.assertTrue(authors.startswith("Haibin Wu (Institute of Computing Technology, CAS)"))

    def test_paper_div_template_asplos_skips_session_heading(self):
        titles = [title for title, _ in self.parse_fixture("asplos2026.html")]

        self.assertEqual(titles[0], "Towards High-Goodput LLM Serving with Prefill-decode Multiplexing")
        self.assertFalse(any(title.startswith("Session") for title in titles))

    def test_paper_div_template_micro_drops_welcome_message(self):
        titles = [title for title, _ in self.parse_fixture("micro59.html")]

        self.assertEqual(len(titles), 4)
        self.assertEqual(titles[0], "Ray-by-Ray: Fine-Grained Resource Management for GPU Ray Tracing Units")
        self.assertFalse(any("Welcome Message" in title for title in titles))

    def test_researchr_track_page_hpca(self):
        entries = self.parse_fixture("hpca2026.html")
        titles = [title for title, _ in entries]

        self.assertEqual(titles[0], "$C^3$ : CXL Coherence Controllers for Heterogeneous Architectures")
        self.assertNotIn("Cache Coherence and Chiplet Interconnects", titles)  # 分会场标题
        self.assertNotIn("Break", titles)  # 茶歇条目没有作者
        self.assertTrue(entries[0][1].startswith("Anatole Lefort, David Schall"))
        self.assertNotIn("Technical University of Munich", entries[0][1])  # span.prog-aff 不算作者

    def test_researchr_strips_award_badge(self):
        titles = [title for title, _ in self.parse_fixture("ppopp2026.html")]

        self.assertEqual(titles[0], "Binary Compatible Critical Section Delegation")

    def test_usenix_technical_sessions(self):
        entries = self.parse_fixture("fast26.html")
        titles = [title for title, _ in entries]

        self.assertEqual(len(titles), 3)
        self.assertEqual(titles[1], "Cost-efficient Archive Cloud Storage with Tape: Design and Deployment")
        self.assertNotIn("Cloud Technologies I", titles)  # 分会场标题
        self.assertFalse(any("Test of Time" in title for title in titles))
        self.assertTrue(entries[0][1].startswith("Leping Yang, Shanghai Jiao Tong University"))

    def test_unknown_layout_falls_back_to_heading_heuristic(self):
        html = "<h2>Session 1: Caches</h2><h3>A Very Long Paper Title About Cache Replacement</h3>"

        self.assertEqual(
            self.module.parse_program_page(html),
            [("A Very Long Paper Title About Cache Replacement", "")],
        )

    def test_program_page_urls(self):
        specs = {spec["slug"]: spec for spec in self.module.VENUE_SPECS}

        self.assertEqual(self.module.program_page_url(specs["micro"], 2026), "https://microarch.org/micro59/program/")
        self.assertEqual(
            self.module.program_page_url(specs["hpca"], 2026),
            "https://conf.researchr.org/track/hpca-2026/hpca-2026-main-conference",
        )
        self.assertEqual(
            self.module.program_page_url(specs["fast"], 2026),
            "https://www.usenix.org/conference/fast26/technical-sessions",
        )

    def test_fetch_program_papers_uses_parsers_and_falls_back_to_last_year(self):
        today = date.today()
        specs = {spec["slug"]: spec for spec in self.module.VENUE_SPECS}
        pages = {
            self.module.program_page_url(specs["micro"], today.year): "micro59.html",
            # 今年的 ISCA 程序页还没上线 → 用去年的
            self.module.program_page_url(specs["isca"], today.year - 1): "isca2026.html",
        }

        def fake_fetch(url, timeout=30, retries=2):
            name = pages.get(url)
            return (PROGRAM_FIXTURES / name).read_text(encoding="utf-8") if name else ""

        with patch.object(self.module, "fetch_url", side_effect=fake_fetch), \
                patch.object(self.module, "score_paper", return_value=10):
            papers = self.module.fetch_conference_program_papers(today)

        venues = {paper["venue"] for paper in papers}
        self.assertEqual(venues, {f"MICRO {today.year}", f"ISCA {today.year - 1}"})
        self.assertEqual(len(papers), 8)
        self.assertTrue(all(paper["authors"] for paper in papers))

    def test_dblp_bot_challenge_stops_after_first_request(self):
        challenge = '<html><script id="anubis_challenge" type="application/json">{}</script></html>'

        with patch.object(self.module, "fetch_url", return_value=challenge) as fetch:
            papers = self.module.fetch_dblp_papers(date(2026, 10, 24))

        self.assertEqual(papers, [])
        self.assertEqual(fetch.call_count, 1)

    def test_select_with_quota_keeps_highest_scoring_venue_papers(self):
        # 插入顺序按 VENUE_SPECS：低分的 ISCA 在前、高分的 MICRO 在后
        candidates = (
            [{"source": "conference-program", "venue": "ISCA 2026", "score": 4, "title": f"isca{i}"} for i in range(3)]
            + [{"source": "conference-program", "venue": "MICRO 2026", "score": 9, "title": f"micro{i}"} for i in range(3)]
            + [{"source": "arxiv", "score": 5, "title": f"a{i}"} for i in range(10)]
        )

        top = self.module.select_with_quota(candidates, top_n=40, dblp_max_ratio=0.1)  # 4 个会议名额，A 会每个 1 个

        venue_titles = {p["title"] for p in top if p["source"] != "arxiv"}
        self.assertEqual(venue_titles, {"micro0", "isca0"})

    def test_select_with_quota_caps_each_venue_by_ccf_rank(self):
        def venue_papers(venue, n):
            return [{"source": "conference-program", "venue": venue, "score": 20, "title": f"{venue}{i}"} for i in range(n)]

        candidates = venue_papers("MICRO 2026", 30) + venue_papers("PACT 2026", 30) + venue_papers("Some Workshop", 30)
        candidates += [{"source": "arxiv", "score": 1, "title": f"a{i}"} for i in range(100)]

        top = self.module.select_with_quota(candidates, top_n=140, dblp_max_ratio=0.4)  # 56 个会议名额

        counts = {}
        for paper in top:
            counts[paper.get("venue")] = counts.get(paper.get("venue"), 0) + 1
        self.assertEqual(counts["MICRO 2026"], 14)  # CCF-A: 25%
        self.assertEqual(counts["PACT 2026"], 5)  # CCF-B: 10%
        self.assertEqual(counts["Some Workshop"], 2)  # 不在 CCF 目录: 5%
        self.assertEqual(len(top), 121)  # 空出来的会议名额没被占满，arXiv 只有 100 篇


if __name__ == "__main__":
    unittest.main()
