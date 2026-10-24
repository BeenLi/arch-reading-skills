#!/usr/bin/env python3
"""Turn a venue string into a short label such as ``MICRO'25``.

Zotero stores venues as full names that differ from year to year ("2022 55th
IEEE/ACM International Symposium on Microarchitecture (MICRO)", "MICRO-54: …",
"Proceedings of the 56th Annual …"), and older notes hold hand-written forms
("MICRO 2025", "IEEE TVLSI"). ``short_venue`` maps all of them to one
abbreviation; ``venue_label`` adds a two-digit year. Unknown venues return
None so callers leave the label out instead of guessing.

Workshops are labeled too, marked with ``-W`` (``SIGCOMM-W'24``,
``HotNets-W'10``); companion volumes with ``-C`` (``WWW-C'19``). A workshop
attached to a main conference takes that conference's name.

Rules are tried in order, so specific names come before the ones they contain:
named workshops before attached ones, journals such as TCAD before the ICCAD
conference, ISCAS before ISCA, the IEEE Micro journal before MICRO.
"""

from __future__ import annotations

import argparse
import re
import sys

_I = re.IGNORECASE

# Workshops with their own identity; the -W marker is added here.
_NAMED_WORKSHOPS: list[tuple[str, str, int]] = [
    ("HotNets", r"Hot Topics in Networks|\bHotNets\b", _I),
    ("HotOS", r"Hot Topics in Operating Systems|\bHotOS\b", _I),
    ("HotStorage", r"Hot Topics in Storage and File Systems|\bHotStorage\b", _I),
    ("HotCloud", r"\bHotCloud\b", _I),
    ("DaMoN", r"Data Management on New Hardware|\bDaMoN\b", _I),
    ("NoCArc", r"Network on Chip Architectures|\bNoCArc\b", _I),
    ("SHAW", r"SoCs, Heterogeneous Architectures and Workloads|\bSHAW\b", _I),
    ("EuroMLSys", r"\bEuroMLSys\b", _I),
]
_WORKSHOP = re.compile(r"\bWorkshops?\b", _I)
_COMPANION = re.compile(r"^Companion\b", _I)

# (abbreviation, pattern, flags) for journals, conferences and preprints.
_RULES: list[tuple[str, str, int]] = [
    # Journals and magazines.
    ("TCAD", r"Computer-Aided Design of Integrated Circuits|\bTCAD\b", _I),
    ("TVLSI", r"Very Large Scale Integration \(VLSI\) Systems|\bTVLSI\b|Trans\. VLSI", _I),
    ("TCAS-I", r"Circuits and Systems I\b|\bTCAS-I\b", _I),
    ("TPDS", r"Transactions on Parallel and Distributed Systems|\bTPDS\b", _I),
    ("TC", r"^IEEE Transactions on Computers$|^IEEE TC$", _I),
    ("CAL", r"Computer Architecture Letters|^(IEEE )?CAL$", _I),
    ("TACO", r"Transactions on Architecture and Code Optimization|Trans\. Archit\. Code Optim|\bTACO\b", _I),
    ("TOCS", r"Transactions on Computer Systems|Trans\. Comput\. Syst", _I),
    ("TODS", r"Transactions on Database Systems|Trans\. Database Syst", _I),
    ("TOS", r"Transactions on Storage|Trans\. Storage", _I),
    ("TOPC", r"Transactions on Parallel Computing", _I),
    ("ToN", r"(?i:Transactions on Networking|Trans\. Netw\.)|\bToN\b", 0),  # 缩写区分大小写，避免误中 "ton"
    ("JSAC", r"Selected Areas in Communications|\bJSAC\b", _I),
    ("TKDD", r"Transactions on Knowledge Discovery from Data", _I),
    ("TKDE", r"Transactions on Knowledge and Data Engineering", _I),
    ("TNNLS", r"Neural Networks and Learning Systems", _I),
    ("TAI", r"Transactions on Artificial Intelligence", _I),
    ("TBD", r"Transactions on Big Data", _I),
    ("TCPMT", r"Components, Packaging and Manufacturing", _I),
    ("JETC", r"Emerg\. Technol\. Comput\. Syst|Emerging Technologies in Computing", _I),
    ("JSSC", r"Journal of Solid-State Circuits|\bJSSC\b", _I),
    ("CSUR", r"Computing Surveys|Comput\. Surv|ACM 计算调查", _I),
    ("CACM", r"Communications of the ACM|Commun\. ACM", _I),
    ("SIGARCH CAN", r"Comput(?:er|\.)? ?Archit(?:ecture|\.)? News", _I),
    ("SIGPLAN Notices", r"SIGPLAN Not(?:ices|\.)", _I),
    ("OSR", r"Operating Systems Review|Oper\. Syst\. Rev", _I),
    ("PER", r"Performance Evaluation Review", _I),
    ("PVLDB", r"Proceedings of the VLDB Endowment|Proc\. VLDB Endow", _I),
    ("VLDBJ", r"The VLDB Journal", _I),
    ("JSA", r"Journal of Systems Architecture", _I),
    ("FGCS", r"Future Generation Computer Systems", _I),
    ("JILP", r"Instruction-Level Parallelism", _I),
    ("IBM JRD", r"IBM Journal of Research and Development", _I),
    ("IBM SJ", r"IBM Systems Journal", _I),
    ("SPM", r"Signal Processing Magazine", _I),
    ("Proc. IEEE", r"^Proceedings of the IEEE$", _I),
    ("IEEE Access", r"IEEE Access", _I),
    ("IRE TEC", r"IRE Transactions on Electronic Computers", _I),
    ("Electronics", r"^Electronics$", _I),
    ("IEEE Computer", r"^(IEEE )?Computer$", 0),
    ("ACM Queue", r"^(ACM )?Queue$", 0),
    # Title case "Micro" is the IEEE Micro magazine; upper case MICRO is the conference.
    ("IEEE Micro", r"^(IEEE )?Micro(?: \d{4})?$", 0),
    # Conferences.
    ("ISCAS", r"International Symposium on Circuits and Systems|\bISCAS\b", _I),
    ("HPCA", r"High[- ]Performance Comp(?:uter)? Architecture|\bHPCA\b", _I),
    ("ISCA", r"Symposium on Computer Architecture|symposia on Computer architecture|\bISCA\b", _I),
    ("MICRO", r"Symposium on Microarchitecture|^MICRO\b|\bMICRO-\d+", _I),
    ("ASPLOS", r"Architectural Support for Programming Languages|\bASPLOS", _I),
    ("ISPASS", r"Performance Analysis of Systems (?:and|&) Software|\bISPASS\b", _I),
    ("IISWC", r"Workload Characterization|\bIISWC\b", _I),
    ("PACT", r"Parallel Architectures? and Compilation|\bPACT\b", _I),
    ("HOTI", r"High-Performance Interconnects|Hot Interconnects|\bHOTI\b", _I),
    ("Hot Chips", r"Hot Chips", _I),
    ("DAC", r"Design Automation Conference|\bDAC\b", _I),
    ("DATE", r"Design,? Automation (?:and|&) Test in Europe|\bDATE\b", 0),
    ("ICCAD", r"Conference on Computer[- ]Aided Design|\bICCAD\b", _I),
    ("ICCD", r"International Conference on Computer Design|\bICCD\b", _I),
    ("FCCM", r"Field[- ]Programmable Custom Computing Machines|\bFCCM\b", _I),
    ("FPGA", r"Symposium on Field[- ]Programmable Gate Arrays|^FPGA\b", _I),
    ("GLSVLSI", r"Great Lakes Symposium on VLSI|\bGLSVLSI\b", _I),
    ("CICC", r"Custom Integrated Circuits Conference|\bCICC\b", _I),
    ("VLSI", r"Symposium on VLSI Technology and Circuits|Symposium on VLSI Circuits|\bVLSI Symposium\b", _I),
    ("ISLPED", r"Low Power Electronics and Design|\bISLPED\b", _I),
    ("NOCS", r"Symposium on Networks-on-Chip|\bNOCS\b", _I),
    ("MEMSYS", r"International Symposium on Memory Systems|\bMEMSYS\b", _I),
    ("CGO", r"Code Generation and Optimization|\bCGO\b", _I),
    ("ISSCC", r"Solid-State Circuits Conference|\bISSCC\b", _I),
    ("SC", r"International Conference for High Performance Computing, Network|\bSC ?'\d\d\b|^SC\d{2}\b", _I),
    ("ICS", r"International Conference on Supercomputing|^ICS\b", _I),
    ("IPDPS", r"Parallel and Distributed Processing Symposium|Symposium on Parallel and Distributed Processing|\bIPDPS\b", _I),
    ("HPDC", r"High-Performance Parallel and Distributed Computing|\bHPDC\b", _I),
    ("HiPC", r"Annual International Conference on High Performance Computing$|\bHiPC\b", _I),
    ("HPCC", r"High Performance Computing (?:&|and) Communications", _I),
    ("ICPP", r"International Conference on Parallel Processing|\bICPP\b", _I),
    ("Euro-Par", r"Euro-Par", _I),
    ("PPoPP", r"Principles and Practice of Parallel Programming|\bPPoPP\b", _I),
    ("SPAA", r"Parallelism in Algorithms and Architectures|\bSPAA\b", _I),
    ("PODC", r"Principles of Distributed Computing|\bPODC\b", _I),
    ("CLUSTER", r"Conference on Cluster Computing", _I),
    ("SOSP", r"Symposium on Operating Systems Principles|\bSOSP\b", _I),
    ("OSDI", r"Operating Systems Design and Implementation|\bOSDI\b", _I),
    ("NSDI", r"Networked Systems Design and Implementation|\bNSDI\b", _I),
    ("ATC", r"USENIX Annual Technical Conference|USENIX ATC|^ATC\b", _I),
    ("EuroSys", r"European Conference on Computer Systems|\bEuroSys\b", _I),
    ("FAST", r"File and Storage Technologies|\bFAST '?(?:\d{4}|\d\d)\b", _I),
    ("SoCC", r"Symposium on Cloud Computing|\bSoCC\b", _I),
    ("MLSys", r"Conference on Machine Learning and Systems|Proceedings of Machine Learning and Systems|\bMLSys\b", _I),
    ("NeurIPS", r"Neural Information Processing Systems|\bNeurIPS\b|\bNIPS\b", _I),
    ("ICML", r"International Conference on Machine Learning(?! and Systems)|\bICML\b", _I),
    ("ICLR", r"Learning Representations|\bICLR\b", _I),
    ("SOSR", r"Symposium on SDN Research|\bSOSR\b", _I),
    ("SIGCOMM", r"Special Interest Group on Data Communication|\bSIGCOMM\b", _I),
    ("INFOCOM", r"\bINFOCOM\b", _I),
    ("ICNP", r"International Conference on Network Protocols|\bICNP\b", _I),
    ("CoNEXT", r"Emerging Networking Experiments|\bCoNEXT\b|ACM on Networking", _I),
    ("SIGMOD", r"International Conference on Management of Data|ACM on Management of Data|\bSIGMOD\b", _I),
    ("WWW", r"World Wide Web Conference|ACM Web Conference|The Web Conference", _I),
    ("ICDE", r"International Conference on Data Engineering|\bICDE\b", _I),
    ("ICPE", r"International Conference on Performance Engineering|\bICPE\b", _I),
    ("PADS", r"Principles of Advanced Discrete Simulation", _I),
    ("CF", r"Computing Frontiers", _I),
    ("SAMOS", r"Embedded Computer Systems: Architectures, Modeling,? and Simulation|\bSAMOS\b", _I),
    ("ReConFig", r"ReConFigurable Computing and FPGAs", _I),
    ("NAS", r"Networking, Architecture,? and Storage", _I),
    ("APCCAS", r"Asia Pacific Conference on Circuits and Systems|\bAPCCAS\b", _I),
    ("BigData", r"International Conference on Big Data", _I),
    ("SIGGRAPH", r"\bSIGGRAPH\b", _I),
    # Preprints.
    ("arXiv", r"\barXiv\b", _I),
    ("SSRN", r"Social Science Research Network|\bSSRN\b", _I),
]
_COMPILED_WORKSHOPS = [(abbr, re.compile(pattern, flags)) for abbr, pattern, flags in _NAMED_WORKSHOPS]
_COMPILED = [(abbr, re.compile(pattern, flags)) for abbr, pattern, flags in _RULES]
_YEAR = re.compile(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)")


def _clean(raw: str) -> str:
    return re.sub(r"\s+", " ", raw.replace("{", "").replace("}", "")).strip().strip("\"'").strip()


def short_venue(raw: str | None) -> str | None:
    """The venue's abbreviation, or None when it is unknown or deliberately not labeled."""
    if not raw:
        return None
    text = _clean(raw)
    for abbr, pattern in _COMPILED_WORKSHOPS:
        if pattern.search(text):
            return f"{abbr}-W"
    host = next((abbr for abbr, pattern in _COMPILED if pattern.search(text)), None)
    if _WORKSHOP.search(text):
        return f"{host}-W" if host else None
    if _COMPANION.search(text):
        return f"{host}-C" if host else None
    return host


def pick_venue(candidates) -> str:
    """First candidate field that names a known venue, else the first non-empty one.

    Zotero items often hold a truncated conferenceName next to a complete
    proceedingsTitle; taking the first non-empty field would pick the junk.
    """
    values = [value for value in candidates if value]
    return next((value for value in values if short_venue(value)), values[0] if values else "")


def _year(value) -> int | None:
    if value is None:
        return None
    match = _YEAR.search(str(value))
    return int(match.group(1)) if match else None


def venue_label(venue: str | None, year=None) -> str | None:
    """``MICRO'25``-style label; the year falls back to one written in the venue string."""
    abbr = short_venue(venue)
    number = _year(year) or _year(venue)
    if abbr is None or number is None:
        return None
    return f"{abbr}'{number % 100:02d}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--venue", required=True, help="venue as stored in Zotero or a note")
    parser.add_argument("--year", help="publication year or date")
    parser.add_argument("--short", action="store_true", help="print only the abbreviation, without the year")
    args = parser.parse_args(argv)

    result = short_venue(args.venue) if args.short else venue_label(args.venue, args.year)
    if result is None:
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
