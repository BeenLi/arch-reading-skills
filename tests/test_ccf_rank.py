import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "skills" / "_shared" / "scripts"))

from ccf_rank import ccf_rank  # noqa: E402


class CcfRankTest(unittest.TestCase):
    def test_short_and_full_venue_names_find_their_rank(self):
        cases = {
            "ISCA": "A",
            "2024 ACM/IEEE 51st Annual International Symposium on Computer Architecture (ISCA)": "A",
            "USENIX ATC": "A",  # CCF 现在写作 ACM SIGOPS ATC
            "IEEE/ACM ToN": "A",  # CCF 写作 TON
            "IEEE TPDS": "A",
            "SC": "A",
            "Proceedings of the VLDB Endowment": "A",
            "2019 28th International Conference on Parallel Architectures and Compilation Techniques (PACT)": "B",
            "Hot Chips": "B",
            "2024 IEEE International Symposium on Performance Analysis of Systems and Software (ISPASS)": "C",
            "2023 17th IEEE/ACM International Symposium on Networks-on-Chip (NOCS)": "C",
        }
        for venue, rank in cases.items():
            with self.subTest(venue=venue):
                self.assertEqual(ccf_rank(venue), rank)

    def test_unlisted_workshops_and_preprints_have_no_rank(self):
        for venue in ("arXiv", "MLSys", "IEEE Micro",
                      "Proceedings of the 9th ACM SIGCOMM Workshop on Hot Topics in Networks", "", None):
            with self.subTest(venue=venue):
                self.assertIsNone(ccf_rank(venue))


class VenueTierScoringTest(unittest.TestCase):
    def setUp(self):
        path = REPO_ROOT / "skills" / "daily-papers" / "scripts" / "fetch_and_score.py"
        spec = importlib.util.spec_from_file_location("fetch_and_score_ccf", path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.module.KEYWORDS, self.module.DOMAIN_BOOST_KEYWORDS, self.module.FOCUS_PHRASES = ["cache"], [], []
        self.module.NEGATIVE_KEYWORDS = []
        self.module.VENUE_RANK_SCORES = {"A": 3, "B": 2, "C": 1}

    def score(self, venue, source="", title="A Cache Paper"):
        return self.module.score_paper({"title": title, "abstract": "", "venue": venue, "source": source})

    def test_venue_points_follow_ccf_tier(self):
        # 标题命中关键词 "cache" 得 3 分，再按 CCF 等级加 venue 分
        self.assertEqual(self.score("MICRO"), 3 + 3)
        self.assertEqual(self.score("PACT"), 3 + 2)
        self.assertEqual(self.score("ISPASS"), 3 + 1)
        self.assertEqual(self.score("MLSys"), 3)
        self.assertEqual(self.score(""), 3)

    def test_source_name_alone_earns_no_venue_points(self):
        # 旧实现按子串匹配 slug，"semantic-scholar" 里含 "sc" 会被当成 SC
        self.assertEqual(self.score("", source="semantic-scholar"), 3)

    def test_venue_alone_cannot_carry_an_off_topic_entry(self):
        # 程序页里的 "Breakfast (Provided)" 挂在 ISCA 下面，也不能靠 CCF-A 的分进推荐
        self.assertEqual(self.score("ISCA", title="Breakfast (Provided) at the Conference Venue"), 0)



class ProgramPageAndNetworkTest(unittest.TestCase):
    def setUp(self):
        path = REPO_ROOT / "skills" / "daily-papers" / "scripts" / "fetch_and_score.py"
        spec = importlib.util.spec_from_file_location("fetch_and_score_net", path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_program_schedule_entries_are_not_titles(self):
        html = "".join(f"<h3>{t}</h3>" for t in (
            "Breakfast (Provided) for All Attendees",
            "Coffee & Snack Break (Provided)",
            "SIGARCH-TCCA Business Meeting and Updates",
            "June 27– July 1, 2026 in Raleigh, North Carolina",
            "Index of /sigcomm/2026/program/",
            "Proba: A Low-Traffic Probabilistic Spatial Memory Streaming Prefetcher",
        ))
        self.assertEqual(self.module.extract_program_titles(html),
                         ["Proba: A Low-Traffic Probabilistic Spatial Memory Streaming Prefetcher"])

    def test_dropped_connections_are_retried(self):
        from unittest.mock import MagicMock, patch
        from urllib.error import URLError

        ok = MagicMock()
        ok.__enter__.return_value.read.return_value = b"<feed/>"
        with patch.object(self.module, "urlopen", side_effect=[URLError("TLS EOF"), ok]), \
                patch.object(self.module.time, "sleep"):
            self.assertEqual(self.module.fetch_url("https://export.arxiv.org/api/query"), "<feed/>")


if __name__ == "__main__":
    unittest.main()
