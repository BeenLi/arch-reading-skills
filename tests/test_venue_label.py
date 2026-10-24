import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "_shared" / "scripts"))

from venue_label import main, pick_venue, short_venue, venue_label  # noqa: E402

# Real venue strings taken from the Zotero library and existing note frontmatter.
KNOWN = {
    "2022 55th IEEE/ACM International Symposium on Microarchitecture (MICRO)": "MICRO",
    "MICRO-54: 54th Annual IEEE/ACM International Symposium on Microarchitecture": "MICRO",
    "Micro-42: The 42nd Annual IEEE/ACM International Symposium on Microarchitecture": "MICRO",
    "Proceedings of the 56th Annual IEEE/ACM International Symposium on Microarchitecture": "MICRO",
    "MICRO 2025": "MICRO",
    "Proceedings of the 49th Annual International Symposium on Computer Architecture": "ISCA",
    "2024 ACM/IEEE 51st Annual International Symposium on Computer Architecture (ISCA)": "ISCA",
    "ISCA '22: The 49th Annual International Symposium on Computer Architecture": "ISCA",
    "2023 IEEE International Symposium on Circuits and Systems (ISCAS)": "ISCAS",
    "2017 IEEE International Symposium on High Performance Computer Architecture (HPCA)": "HPCA",
    "IEEE International Symposium on High-Performance Comp Architecture": "HPCA",
    "Proceedings of the 28th ACM International Conference on Architectural Support for Programming Languages and Operating Systems": "ASPLOS",
    "ASPLOS '26: 31st ACM International Conference on Architectural Support for Programming Languages": "ASPLOS",
    "ASPLOS 2026": "ASPLOS",
    "2014 IEEE International Symposium on Performance Analysis of Systems and Software (ISPASS)": "ISPASS",
    "2007 IEEE International Symposium on Performance Analysis of Systems & Software": "ISPASS",
    "2024 IEEE International Symposium on Workload Characterization (IISWC)": "IISWC",
    "2019 28th International Conference on Parallel Architectures and Compilation Techniques (PACT)": "PACT",
    "2022 IEEE Symposium on High-Performance Interconnects (HOTI)": "HOTI",
    '"HOTI 2023"': "HOTI",
    "2023 60th ACM/IEEE Design Automation Conference (DAC)": "DAC",
    "2018 Design, Automation & Test in Europe Conference & Exhibition (DATE)": "DATE",
    "2021 IEEE/ACM International Conference On Computer Aided Design (ICCAD)": "ICCAD",
    "2022 IEEE 40th International Conference on Computer Design (ICCD)": "ICCD",
    "Proceedings of the 2016 ACM/SIGDA International Symposium on Field-Programmable Gate Arrays": "FPGA",
    "2023 IEEE 31st Annual International Symposium on Field-Programmable Custom Computing Machines (FCCM)": "FCCM",
    "Proceedings of the International Conference for High Performance Computing, Networking, Storage and Analysis": "SC",
    "SC '15: Proceedings of the International Conference for High Performance Computing, Networking, Storage and Analysis": "SC",
    "2020 IEEE International Parallel and Distributed Processing Symposium (IPDPS)": "IPDPS",
    '"IPDPS 2024"': "IPDPS",
    "Proceedings of the 2016 International Conference on Supercomputing": "ICS",
    "Proceedings of the 25th ACM SIGPLAN Symposium on Principles and Practice of Parallel Programming": "PPoPP",
    "Proceedings of the 29th Symposium on Operating Systems Principles": "SOSP",
    "SOSP 2023": "SOSP",
    "14th USENIX Symposium on Operating Systems Design and Implementation (OSDI 20)": "OSDI",
    "15th {USENIX} Symposium on Operating Systems Design and Implementation ({OSDI} 21)": "OSDI",
    "OSDI": "OSDI",
    "22nd USENIX Symposium on Networked Systems Design and Implementation (NSDI 25)": "NSDI",
    "2021 USENIX Annual Technical Conference (USENIX ATC 21)": "ATC",
    "USENIX ATC": "ATC",
    "Proceedings of the Eighteenth European Conference on Computer Systems": "EuroSys",
    "Proceedings of the Fourteenth EuroSys Conference 2019": "EuroSys",
    "Eighth Conference on Machine Learning and Systems": "MLSys",
    "Proceedings of the ACM SIGCOMM 2025 Conference": "SIGCOMM",
    "SIGCOMM '17: ACM SIGCOMM 2017 Conference": "SIGCOMM",
    "Proceedings of the 2018 Conference of the ACM Special Interest Group on Data Communication": "SIGCOMM",
    "ACM SIGCOMM 2024": "SIGCOMM",
    "Proceedings of the ACM SIGCOMM Symposium on SDN Research (SOSR)": "SOSR",
    # Workshops are labeled, marked with -W; companion volumes with -C.
    "Proceedings of the 9th ACM SIGCOMM Workshop on Hot Topics in Networks": "HotNets-W",
    "Proceedings of the 15th ACM Workshop on Hot Topics in Storage and File Systems": "HotStorage-W",
    "Proceedings of the Workshop on Hot Topics in Operating Systems": "HotOS-W",
    "2022 15th IEEE/ACM International Workshop on Network on Chip Architectures (NoCArc)": "NoCArc-W",
    "3rd Workshop on SoCs, Heterogeneous Architectures and Workloads (SHAW-3)": "SHAW-W",
    "Proceedings of the 2024 SIGCOMM Workshop on Networks for AI Computing": "SIGCOMM-W",
    "Proceedings of the SC '23 Workshops of The International Conference on High Performance Computing, Network, Storage, and Analysis": "SC-W",
    "2012 IEEE 26th International Parallel and Distributed Processing Symposium Workshops & PhD Forum": "IPDPS-W",
    "Companion Proceedings of The 2019 World Wide Web Conference": "WWW-C",
    "Companion of the ACM/SPEC International Conference on Performance Engineering": "ICPE-C",
    "Proceedings of the ACM Web Conference 2023": "WWW",
    "IEEE INFOCOM 2025 - IEEE Conference on Computer Communications": "INFOCOM",
    "Proceedings of the 2014 ACM SIGMOD International Conference on Management of Data": "SIGMOD",
    "2018 IEEE 34th International Conference on Data Engineering (ICDE)": "ICDE",
    "IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems": "TCAD",
    "IEEE TCAD": "TCAD",
    "IEEE Transactions on Very Large Scale Integration (VLSI) Systems": "TVLSI",
    "IEEE TVLSI": "TVLSI",
    "IEEE Transactions on Circuits and Systems I: Regular Papers": "TCAS-I",
    "IEEE TCAS-I": "TCAS-I",
    "IEEE Transactions on Parallel and Distributed Systems": "TPDS",
    "IEEE Transactions on Computers": "TC",
    "IEEE Computer Architecture Letters": "CAL",
    "IEEE CAL": "CAL",
    "ACM Transactions on Architecture and Code Optimization": "TACO",
    "ACM Trans. Archit. Code Optim.": "TACO",
    "ACM TACO": "TACO",
    "ACM Computing Surveys (CSUR)": "CSUR",
    "Proceedings of the VLDB Endowment": "PVLDB",
    "IEEE Micro": "IEEE Micro",
    "Micro": "IEEE Micro",
    '"IEEE Micro 2024"': "IEEE Micro",
    "IEEE Access": "IEEE Access",
    "IRE Transactions on Electronic Computers": "IRE TEC",
    "Electronics": "Electronics",
    "arXiv": "arXiv",
    '"arXiv preprint"': "arXiv",
    "Social Science Research Network": "SSRN",
    # Architecture / LLM-systems venues added for the default daily-papers theme.
    "Proceedings of the 2024 ACM/SIGDA International Symposium on Field Programmable Gate Arrays": "FPGA",
    "2024 IEEE Symposium on VLSI Technology and Circuits": "VLSI",
    "Proceedings of the 29th ACM/IEEE International Symposium on Low Power Electronics and Design": "ISLPED",
    "2023 17th IEEE/ACM International Symposium on Networks-on-Chip (NOCS)": "NOCS",
    "Proceedings of the International Symposium on Memory Systems": "MEMSYS",
    "2024 IEEE/ACM International Symposium on Code Generation and Optimization (CGO)": "CGO",
    "22nd USENIX Conference on File and Storage Technologies (FAST 24)": "FAST",
    "Proceedings of the 2024 ACM Symposium on Cloud Computing": "SoCC",
    "Proceedings of Machine Learning and Systems": "MLSys",
    "Proceedings of the 4th Workshop on Machine Learning and Systems (EuroMLSys)": "EuroMLSys-W",
    "Advances in Neural Information Processing Systems": "NeurIPS",
    "Proceedings of the 41st International Conference on Machine Learning": "ICML",
    "The Twelfth International Conference on Learning Representations": "ICLR",
    "Proceedings of the ACM on Networking (CoNEXT)": "CoNEXT",
    "Proceedings of the ACM on Management of Data": "SIGMOD",
    "IEEE/ACM Transactions on Networking": "ToN",
    "IEEE Journal on Selected Areas in Communications": "JSAC",
}

# Non-venues, and workshops whose host or name we cannot tell, are not labeled.
UNKNOWN = [
    "Proceedings of the 3rd International Workshop on Something Obscure",
    "the 30th annual international symposium",
    "ResearchGate",
    "ETH Zurich",
    "Fast Company",
    '"Notes"',
    "",
    None,
]


class ShortVenueTest(unittest.TestCase):
    def test_known_venues(self):
        for raw, expected in KNOWN.items():
            with self.subTest(raw=raw):
                self.assertEqual(short_venue(raw), expected)

    def test_unknown_venues(self):
        for raw in UNKNOWN:
            with self.subTest(raw=raw):
                self.assertIsNone(short_venue(raw))


class PickVenueTest(unittest.TestCase):
    def test_first_recognizable_field_wins(self):
        # conferenceName is truncated junk; proceedingsTitle is complete.
        candidates = ["", "the 30th annual international symposium", "Proceedings of the 30th annual international symposium on Computer architecture - ISCA '03"]
        self.assertEqual(pick_venue(candidates), candidates[2])

    def test_falls_back_to_the_first_non_empty_field(self):
        self.assertEqual(pick_venue(["", "ResearchGate", "Notes"]), "ResearchGate")
        self.assertEqual(pick_venue(["", None]), "")


class VenueLabelTest(unittest.TestCase):
    def test_conference_label_uses_two_digit_year(self):
        self.assertEqual(venue_label("2022 55th IEEE/ACM International Symposium on Microarchitecture (MICRO)", 2025), "MICRO'25")

    def test_year_may_be_a_string_or_a_date(self):
        self.assertEqual(venue_label("ISCA", "2005"), "ISCA'05")
        self.assertEqual(venue_label("ISCA", "2024-06-29"), "ISCA'24")

    def test_workshop_label_keeps_the_marker_before_the_year(self):
        self.assertEqual(venue_label("Proceedings of the 2024 SIGCOMM Workshop on Networks for AI Computing", 2024), "SIGCOMM-W'24")

    def test_journal_and_preprint_labels(self):
        self.assertEqual(venue_label("IEEE Access", 2024), "IEEE Access'24")
        self.assertEqual(venue_label("arXiv preprint", 2026), "arXiv'26")

    def test_year_falls_back_to_one_written_in_the_venue(self):
        self.assertEqual(venue_label("MICRO 2025", None), "MICRO'25")

    def test_no_label_without_a_known_venue_or_a_year(self):
        self.assertIsNone(venue_label("ResearchGate", 2024))
        self.assertIsNone(venue_label("ISCA", None))
        self.assertIsNone(venue_label("ISCA", "n.d."))


class CliTest(unittest.TestCase):
    def run_main(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(list(argv))
        return code, out.getvalue().strip()

    def test_prints_label(self):
        self.assertEqual(self.run_main("--venue", "Proceedings of the ACM SIGCOMM 2025 Conference", "--year", "2025"), (0, "SIGCOMM'25"))

    def test_short_only(self):
        self.assertEqual(self.run_main("--venue", "IEEE Transactions on Computers", "--short"), (0, "TC"))

    def test_unknown_exits_1(self):
        code, out = self.run_main("--venue", "ResearchGate", "--year", "2024")
        self.assertEqual((code, out), (1, ""))


if __name__ == "__main__":
    unittest.main()
