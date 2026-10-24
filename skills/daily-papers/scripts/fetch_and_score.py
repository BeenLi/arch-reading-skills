#!/usr/bin/env python3
"""
fetch_and_score.py — Phase 1+2: fetch, score, dedup, and select top papers.

Usage:
    python3 fetch_and_score.py > /tmp/daily_papers_top30.json
    python3 fetch_and_score.py --date 2026-02-25 > /tmp/daily_papers_top30.json
    python3 fetch_and_score.py --days 7 > /tmp/daily_papers_top30.json

Stderr: progress logs. Stdout: JSON array of selected papers.
"""

import argparse
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from html import unescape
from pathlib import Path
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_SHARED_DIR = Path(__file__).resolve().parents[2] / "_shared" / "scripts"
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))

from ccf_rank import ccf_rank
from user_config import daily_papers_config, daily_papers_dir


_CONFIG = daily_papers_config()

KEYWORDS = _CONFIG["keywords"]
NEGATIVE_KEYWORDS = _CONFIG["negative_keywords"]
DOMAIN_BOOST_KEYWORDS = _CONFIG["domain_boost_keywords"]
ARXIV_CATEGORIES = _CONFIG["arxiv_categories"]
MIN_SCORE = _CONFIG["min_score"]
FOCUS_PHRASES = _CONFIG.get("focus_phrases", [])
VENUE_RANK_SCORES = _CONFIG.get("venue_rank_scores", {})
TOP_N = _CONFIG["top_n"]

DAILYPAPERS_DIR = daily_papers_dir()
HISTORY_PATH = DAILYPAPERS_DIR / ".history.json"

ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}

VENUE_SPECS = [
    {"slug": "isca", "name": "ISCA", "dblp_path": "conf/isca/isca{year}.html", "program_url": "https://iscaconf.org/isca{year}/program/"},
    # MICRO 的网址用届数（2026 年是 MICRO-59），见 program_page_url
    {"slug": "micro", "name": "MICRO", "dblp_path": "conf/micro/micro{year}.html", "program_url": "https://microarch.org/micro{micro_no}/program/"},
    # hpca-conf.org/{year}/program/ 会跳到 researchr 首页（没有论文列表），直接取主会 track 页
    {"slug": "hpca", "name": "HPCA", "dblp_path": "conf/hpca/hpca{year}.html", "program_url": "https://conf.researchr.org/track/hpca-{year}/hpca-{year}-main-conference"},
    {"slug": "asplos", "name": "ASPLOS", "dblp_path": "conf/asplos/asplos{year}.html", "program_url": "https://www.asplos-conference.org/asplos{year}/program/"},
    {"slug": "ppopp", "name": "PPoPP", "dblp_path": "conf/ppopp/ppopp{year}.html", "program_url": "https://conf.researchr.org/track/PPoPP-{year}/PPoPP-{year}-papers"},
    {"slug": "fast", "name": "FAST", "dblp_path": "conf/fast/fast{year}.html", "program_url": "https://www.usenix.org/conference/fast{yy}/technical-sessions"},
    {"slug": "sigcomm", "name": "SIGCOMM", "dblp_path": "conf/sigcomm/sigcomm{year}.html", "program_url": "https://conferences.sigcomm.org/sigcomm/{year}/program/"},
    {"slug": "nsdi", "name": "NSDI", "dblp_path": "conf/nsdi/nsdi{year}.html", "program_url": "https://www.usenix.org/conference/nsdi{yy}/technical-sessions"},
    {"slug": "osdi", "name": "OSDI", "dblp_path": "conf/osdi/osdi{year}.html", "program_url": "https://www.usenix.org/conference/osdi{yy}/technical-sessions"},
    {"slug": "atc", "name": "USENIX ATC", "dblp_path": "conf/usenix/usenix{year}.html", "program_url": "https://www.usenix.org/conference/atc{yy}/technical-sessions"},
    {"slug": "eurosys", "name": "EuroSys", "dblp_path": "conf/eurosys/eurosys{year}.html", "program_url": "https://{year}.eurosys.org/program/"},
    {"slug": "sc", "name": "SC", "dblp_path": "conf/sc/sc{year}.html", "program_url": ""},
    {"slug": "mlsys", "name": "MLSys", "dblp_path": "", "program_url": ""},
]

JOURNAL_SPECS = [
    {"slug": "tpds", "name": "IEEE TPDS", "dblp_path": "journals/tpds/tpds{volume}.html", "base_year": 1990, "base_volume": 1},
    {"slug": "ton", "name": "IEEE/ACM ToN", "dblp_path": "journals/ton/ton{volume}.html", "base_year": 1993, "base_volume": 1},
]

VENUE_MONTH_HINTS = {
    "isca": 6,
    "micro": 10,
    "asplos": 4,
    "sigcomm": 9,
    "nsdi": 4,
    "osdi": 7,
    "atc": 7,
    "eurosys": 4,
    "sc": 11,
    "mlsys": 5,
    "hpca": 3,
    "ppopp": 2,
    "fast": 2,
}


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text or "")).strip()


def normalize_venue_slug(venue: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "", (venue or "").lower())
    aliases = {"usenixatc": "atc"}
    if normalized in aliases:
        return aliases[normalized]

    for spec in VENUE_SPECS:
        if normalized in {
            re.sub(r"[^a-z0-9]+", "", spec["slug"].lower()),
            re.sub(r"[^a-z0-9]+", "", spec["name"].lower()),
        }:
            return spec["slug"]
    return normalized


def placeholder_publication_date(venue: str, year: int) -> str:
    month = VENUE_MONTH_HINTS.get(normalize_venue_slug(venue), 1)
    return f"{year}-{month:02d}-01"


def score_paper(paper: dict) -> int:
    text = (paper.get("title", "") + " " + paper.get("abstract", "")).lower()
    title_lower = paper.get("title", "").lower()

    for neg in NEGATIVE_KEYWORDS:
        if neg.lower() in title_lower:
            return -999

    score = 0
    keyword_hits = 0
    for kw in KEYWORDS:
        kw_lower = kw.lower()
        if kw_lower in title_lower:
            score += 3
            keyword_hits += 1
        elif kw_lower in text:
            score += 1
            keyword_hits += 1

    domain_hits = sum(1 for kw in DOMAIN_BOOST_KEYWORDS if kw.lower() in text)
    if domain_hits >= 4:
        score += 4
    elif domain_hits >= 2:
        score += 2
    elif domain_hits == 1:
        score += 1

    # 重点方向短语（user-config.json 的 focus_phrases）：标题或摘要里出现一个 +1
    score += sum(1 for phrase in FOCUS_PHRASES if phrase.lower() in text)

    # 主题一个都没命中就不给 venue 分：venue 强只是加分项，不能单独把论文（或程序页里的日程条目）送进推荐
    if score == 0:
        return 0

    # 按 CCF 等级给 venue 分（user-config.json 的 venue_rank_scores），不在 CCF 目录里的 venue 不加分
    score += VENUE_RANK_SCORES.get(ccf_rank(paper.get("venue")) or "", 0)

    return score


def retry_delay_from_headers(exc: HTTPError, attempt: int) -> int:
    retry_after = exc.headers.get("Retry-After") if exc.headers else None
    if retry_after and retry_after.isdigit():
        return min(int(retry_after), 60)
    return min(5 * (2 ** attempt), 60)


def fetch_url(url: str, timeout: int = 30, retries: int = 2) -> str:
    retry_statuses = {429, 500, 502, 503, 504}
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers={"User-Agent": "daily-papers-bot/2.0"})
            with urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            if exc.code in retry_statuses and attempt < retries:
                delay = retry_delay_from_headers(exc, attempt)
                print(
                    f"  [WARN] fetch failed {url}: HTTP {exc.code}; retrying in {delay}s",
                    file=sys.stderr,
                )
                time.sleep(delay)
                continue
            print(f"  [WARN] fetch failed {url}: {exc}", file=sys.stderr)
            return ""
        except (URLError, OSError) as exc:
            # 连接被重置 / TLS EOF / 超时这类瞬时网络错误，和 5xx 一样退避重试
            if attempt < retries:
                delay = min(5 * (2 ** attempt), 60)
                print(f"  [WARN] fetch failed {url}: {exc}; retrying in {delay}s", file=sys.stderr)
                time.sleep(delay)
                continue
            print(f"  [WARN] fetch failed {url}: {exc}", file=sys.stderr)
            return ""
        except Exception as exc:
            print(f"  [WARN] fetch failed {url}: {exc}", file=sys.stderr)
            return ""
    return ""


def make_base_paper(title: str, authors: str = "", abstract: str = "", url: str = "", **extra) -> dict:
    paper = {
        "title": title,
        "authors": authors,
        "affiliations": "",
        "abstract": abstract,
        "url": url,
        "pdf": extra.pop("pdf", ""),
        "date": extra.pop("date", ""),
        "score": 0,
        "category": extra.pop("category", ""),
        "source": extra.pop("source", ""),
        "venue": extra.pop("venue", ""),
    }
    paper.update(extra)
    return paper


def venue_label(spec: dict, year: int) -> str:
    return f"{spec['name']} {year}"


def display_venue_name(venue: str) -> str:
    normalized = venue.lower()
    names = {
        "eurosys": "EuroSys",
        "sigcomm": "SIGCOMM",
        "isca": "ISCA",
        "micro": "MICRO",
        "hpca": "HPCA",
        "asplos": "ASPLOS",
        "nsdi": "NSDI",
        "osdi": "OSDI",
        "atc": "USENIX ATC",
        "sc": "SC",
        "mlsys": "MLSys",
        "ppopp": "PPoPP",
        "fast": "FAST",
    }
    return names.get(normalized, venue)


# 会议程序页里的日程条目，不是论文
_PROGRAM_NOISE = re.compile(
    r"\b(breakfast|lunch|dinner|reception|registration|coffee|snack|welcome remarks|welcome message|opening remarks|closing remarks"
    r"|business meeting|meetup|excursion|award|luncheon|social event)\b"
    r"|^index of /"
    r"|\b(symposium|conference)\b.*\b20\d\d\)?$"  # 会议名称行，如 "... Computer Architecture (HPCA) 2026"
    r"|^(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d",
    re.IGNORECASE,
)


def extract_program_titles(html: str) -> list[str]:
    candidates = []
    for pattern in (
        r"<h[1-4][^>]*>(.*?)</h[1-4]>",
        r"<strong[^>]*>(.*?)</strong>",
        r"<span[^>]*class=[\"'][^\"']*title[^\"']*[\"'][^>]*>(.*?)</span>",
    ):
        for match in re.finditer(pattern, html, re.DOTALL | re.IGNORECASE):
            title = normalize_whitespace(strip_tags(match.group(1)))
            if len(title) < 20 or len(title) > 220:
                continue
            if re.match(r"^(session|keynote|break|poster session|coffee break|panel)\b", title, re.IGNORECASE):
                continue
            if _PROGRAM_NOISE.search(title):
                continue
            if not re.search(r"[A-Za-z]{4,}", title):
                continue
            if title not in candidates:
                candidates.append(title)
    return candidates


def _html_text(fragment: str) -> str:
    return normalize_whitespace(strip_tags(fragment or ""))


def _parse_paper_div_program(html: str) -> list[tuple[str, str]]:
    """ISCA / MICRO / ASPLOS 共用的模板：<div class="paper-title"> 后跟 <div class="paper-authors">。"""
    return [
        (_html_text(m.group(1)), _html_text(m.group(2)))
        for m in re.finditer(
            r'<div class="paper-title">(.*?)</div>\s*(?:<div class="paper-authors">(.*?)</div>)?',
            html,
            re.DOTALL,
        )
    ]


def _parse_researchr_program(html: str) -> list[tuple[str, str]]:
    """conf.researchr.org 的 track 页（HPCA / PPoPP）：每个 <tr data-slot-id> 是一个日程条目，
    有 performers（作者）的才是论文；茶歇、颁奖这类条目没有作者。"""
    papers = []
    for row in re.findall(r"<tr data-slot-id=.*?</tr>", html, re.DOTALL):
        title_match = re.search(r'<a href="#" data-event-modal="[^"]+">(.*?)</a>', row, re.DOTALL)
        performers = re.search(r'<div class="performers">(.*?)</div>', row, re.DOTALL)
        if not title_match or not performers:
            continue
        # 标题里嵌着 “Best Paper Award” 之类的徽章
        title = re.sub(r'<span class="pull-right">.*?</span></span></span>', "", title_match.group(1), flags=re.DOTALL)
        authors = [_html_text(a) for a in re.findall(r"<a [^>]*>(.*?)</a>", performers.group(1), re.DOTALL)]
        papers.append((_html_text(title), ", ".join(a for a in authors if a)))
    return papers


def _parse_usenix_program(html: str) -> list[tuple[str, str]]:
    """usenix.org 的 technical-sessions 页（NSDI / OSDI / ATC / FAST）：每篇是 <article class="node node-paper">。"""
    papers = []
    for block in re.findall(r'<article [^>]*class="node node-paper.*?</article>', html, re.DOTALL):
        title_match = re.search(r"<h2[^>]*>\s*<a [^>]*>(.*?)</a>", block, re.DOTALL)
        if not title_match:
            continue
        people = re.search(r'field-name-field-paper-people-text.*?<p>(.*?)</p>', block, re.DOTALL)
        papers.append((_html_text(title_match.group(1)), _html_text(people.group(1)) if people else ""))
    return papers


def parse_program_page(html: str) -> list[tuple[str, str]]:
    """从会议程序页抽 (标题, 作者)。按页面结构选解析器（不按 venue 配置，网址跳转到别的站也能认出来），
    认不出结构时才退回 extract_program_titles 的 <h1-4>/<strong> 启发式（它会混进分会场标题）。"""
    if 'class="paper-title"' in html:
        papers = _parse_paper_div_program(html)
    elif "data-event-modal=" in html:
        papers = _parse_researchr_program(html)
    elif "node node-paper" in html:
        papers = _parse_usenix_program(html)
    else:
        return [(title, "") for title in extract_program_titles(html)]

    seen = set()
    unique = []
    for title, authors in papers:
        if len(title) < 8 or title.lower() in seen or _PROGRAM_NOISE.search(title):
            continue
        seen.add(title.lower())
        unique.append((title, authors))
    return unique


def program_page_url(spec: dict, year: int) -> str:
    return spec["program_url"].format(year=year, yy=str(year)[-2:], micro_no=year - 1967)


def parse_dblp_proceedings_html(html: str, venue: str, year: int) -> list[dict]:
    entries = []
    for match in re.finditer(r"(<li class=\"entry [^\"]*?\".*?)(?=<li class=\"entry |\Z)", html, re.DOTALL):
        block = match.group(1)
        title_match = re.search(r"<span class=\"title\"[^>]*>(.*?)</span>", block, re.DOTALL)
        if not title_match:
            continue

        title = normalize_whitespace(strip_tags(title_match.group(1)))
        tail = block[title_match.end():title_match.end() + 8]
        if tail.lstrip().startswith(".") and not title.endswith("."):
            title += "."
        if not title:
            continue

        authors = [
            normalize_whitespace(strip_tags(author))
            for author in re.findall(r"<span itemprop=\"author\"[^>]*>(.*?)</span>", block, re.DOTALL)
        ]
        links = re.findall(r"<a href=\"([^\"]+)\"", block)
        url = next((link for link in links if "doi.org" in link or "arxiv.org" in link), "")

        entries.append(
            make_base_paper(
                title=title,
                authors=", ".join(author for author in authors if author),
                url=url,
                source="dblp",
                venue=f"{display_venue_name(venue)} {year}",
                date=placeholder_publication_date(venue, year),
            )
        )

    return entries


def parse_journal_html(html: str, journal_name: str, year: int) -> list[dict]:
    entries = []
    for paper in parse_dblp_proceedings_html(html, venue=journal_name, year=year):
        paper["source"] = "dblp-journal"
        paper["venue"] = journal_name
        entries.append(paper)
    return entries


def is_bot_challenge(html: str) -> bool:
    """DBLP 从 2026 年起对脚本返回 Anubis 验证页（HTTP 200/202，没有论文）。"""
    return "anubis_challenge" in (html or "")


def fetch_dblp_papers(target_date, years_back: int = 2) -> list[dict]:
    papers = []
    seen_titles = set()
    current_year = target_date.year

    for spec in VENUE_SPECS:
        if not spec["dblp_path"]:
            continue
        for year in range(current_year, current_year - years_back, -1):
            url = f"https://dblp.org/db/{spec['dblp_path'].format(year=year)}"
            print(f"  Fetching DBLP {spec['name']} {year}...", file=sys.stderr)
            html = fetch_url(url, timeout=30)
            if is_bot_challenge(html):
                print("  [WARN] DBLP is behind a bot challenge; skipping DBLP for this run", file=sys.stderr)
                return papers
            if not html:
                continue
            parsed = parse_dblp_proceedings_html(html, venue=spec["name"], year=year)
            for paper in parsed:
                title_key = paper["title"].lower()
                if title_key in seen_titles:
                    continue
                paper["score"] = score_paper(paper)
                if paper["score"] >= MIN_SCORE:
                    seen_titles.add(title_key)
                    papers.append(paper)

    for spec in JOURNAL_SPECS:
        for year in range(current_year, current_year - years_back, -1):
            volume = spec["base_volume"] + (year - spec["base_year"])
            url = f"https://dblp.org/db/{spec['dblp_path'].format(volume=volume)}"
            print(f"  Fetching DBLP {spec['name']} volume {volume}...", file=sys.stderr)
            html = fetch_url(url, timeout=30)
            if not html:
                continue
            for paper in parse_journal_html(html, journal_name=spec["name"], year=year):
                title_key = paper["title"].lower()
                if title_key in seen_titles:
                    continue
                paper["score"] = score_paper(paper)
                if paper["score"] >= MIN_SCORE:
                    seen_titles.add(title_key)
                    papers.append(paper)

    print(f"  DBLP: {len(papers)} papers after scoring", file=sys.stderr)
    return papers


def fetch_conference_program_papers(target_date) -> list[dict]:
    now = datetime.now().date()
    if (now - target_date).days > 56:
        return []

    papers = []
    seen_titles = set()

    for spec in VENUE_SPECS:
        if not spec["program_url"]:
            continue
        # 今年的程序页还没出（年初）就用去年的
        for year in (target_date.year, target_date.year - 1):
            url = program_page_url(spec, year)
            print(f"  Fetching program page {spec['name']} {year}...", file=sys.stderr)
            entries = parse_program_page(fetch_url(url, timeout=20))
            if entries:
                break
        else:
            continue
        print(f"    {len(entries)} entries", file=sys.stderr)
        for title, authors in entries:
            title_key = title.lower()
            if title_key in seen_titles:
                continue
            paper = make_base_paper(
                title=title,
                authors=authors,
                url=url,
                source="conference-program",
                venue=venue_label(spec, year),
                date=placeholder_publication_date(spec["slug"], year),
            )
            paper["score"] = score_paper(paper)
            if paper["score"] >= MIN_SCORE:
                seen_titles.add(title_key)
                papers.append(paper)

    print(f"  Program pages: {len(papers)} papers after scoring", file=sys.stderr)
    return papers


def fetch_semantic_scholar_papers(target_date, days: int = 1) -> list[dict]:
    query = quote("computer architecture OR memory hierarchy OR multicore OR accelerator OR interconnect OR LLM serving")
    limit = min(30 * days, 100)
    url = (
        "https://api.semanticscholar.org/graph/v1/paper/search"
        f"?query={query}&fields=title,abstract,authors,year,venue,url,externalIds&limit={limit}"
    )
    print("  Fetching Semantic Scholar fallback...", file=sys.stderr)
    raw = fetch_url(url, timeout=30)
    if not raw:
        return []

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print("  [WARN] bad JSON from Semantic Scholar", file=sys.stderr)
        return []

    papers = []
    current_year = target_date.year
    for item in payload.get("data", []):
        year = item.get("year")
        if year and year < current_year - 2:
            continue
        authors = ", ".join(
            author.get("name", "").strip()
            for author in item.get("authors", [])
            if isinstance(author, dict) and author.get("name")
        )
        external_ids = item.get("externalIds") or {}
        arxiv_id = external_ids.get("ArXiv", "")
        url = item.get("url", "")
        paper = make_base_paper(
            title=item.get("title", ""),
            authors=authors,
            abstract=item.get("abstract", "") or "",
            url=url,
            pdf=f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else "",
            source="semantic-scholar",
            venue=item.get("venue", "") or "Semantic Scholar",
            date=f"{year}-01-01" if year else "",
        )
        paper["score"] = score_paper(paper)
        if paper["score"] >= MIN_SCORE:
            papers.append(paper)

    print(f"  Semantic Scholar: {len(papers)} papers after scoring", file=sys.stderr)
    return papers


def fetch_arxiv_papers(start_date=None, end_date=None, days: int = 1) -> list[dict]:
    max_results = min(400 * days, 3000)
    cats = "+OR+".join(f"cat:{c}" for c in ARXIV_CATEGORIES)
    url = (
        f"https://export.arxiv.org/api/query?"
        f"search_query=({cats})"
        f"&sortBy=submittedDate&sortOrder=descending&max_results={max_results}"
    )

    timeout = max(60, 30 * days)
    print(f"  Fetching arXiv (max_results={max_results}, timeout={timeout}s)...", file=sys.stderr)
    xml_text = fetch_url(url, timeout=timeout)
    if not xml_text:
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        print(f"  [WARN] arXiv XML parse error: {exc}", file=sys.stderr)
        return []

    papers = []
    filtered_by_date = 0
    for entry in root.findall("atom:entry", ATOM_NS):
        title_el = entry.find("atom:title", ATOM_NS)
        summary_el = entry.find("atom:summary", ATOM_NS)
        published_el = entry.find("atom:published", ATOM_NS)
        id_el = entry.find("atom:id", ATOM_NS)

        if title_el is None or summary_el is None:
            continue

        title = normalize_whitespace(title_el.text or "")
        abstract = normalize_whitespace(summary_el.text or "")
        entry_url = (id_el.text or "").strip() if id_el is not None else ""
        date = (published_el.text or "")[:10] if published_el is not None else ""

        if days > 1 and start_date and end_date and date:
            try:
                pub_date = datetime.strptime(date, "%Y-%m-%d").date()
                if pub_date < start_date or pub_date > end_date:
                    filtered_by_date += 1
                    continue
            except ValueError:
                pass

        author_els = entry.findall("atom:author", ATOM_NS)
        names = []
        affiliations = set()
        for author in author_els:
            name_el = author.find("atom:name", ATOM_NS)
            if name_el is not None and name_el.text:
                names.append(name_el.text.strip())
            for aff_el in author.findall("arxiv:affiliation", ATOM_NS):
                if aff_el.text and aff_el.text.strip():
                    affiliations.add(aff_el.text.strip())

        cat_el = entry.find("arxiv:primary_category", ATOM_NS)
        category = cat_el.get("term", "") if cat_el is not None else ""
        arxiv_id = entry_url.split("/abs/")[-1] if "/abs/" in entry_url else ""
        paper = make_base_paper(
            title=title,
            authors=", ".join(names),
            abstract=abstract,
            url=entry_url,
            pdf=f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else "",
            date=date,
            category=category,
            source="arxiv",
            venue="arXiv",
            affiliations=", ".join(sorted(affiliations)) if affiliations else "",
        )
        paper["score"] = score_paper(paper)
        if paper["score"] >= 0:
            papers.append(paper)

    print(
        f"  arXiv: {len(papers)} papers after scoring (from {len(root.findall('atom:entry', ATOM_NS))} parsed, {filtered_by_date} filtered by date)",
        file=sys.stderr,
    )
    return papers


def extract_arxiv_id(text: str) -> str:
    """Pull an arXiv id from a string.

    Accepts either an arXiv URL / ``arXiv:xxxx.yyyy`` reference, or a raw
    bare id like ``2501.01234`` (or ``2501.01234v2``). Refuses to match
    digit runs inside unrelated identifiers such as DOIs."""
    text = (text or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if "arxiv" in lowered:
        match = re.search(r"(\d{4}\.\d{4,5})", text)
        return match.group(1) if match else ""
    match = re.fullmatch(r"(\d{4}\.\d{4,5})(?:v\d+)?", text)
    return match.group(1) if match else ""


_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>]+)", re.IGNORECASE)


def extract_doi(text: str) -> str:
    match = _DOI_RE.search(text or "")
    if not match:
        return ""
    return match.group(1).rstrip(".,);").lower()


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (title or "").lower())


def paper_lookup_keys(paper: dict) -> set[str]:
    """Return all lookup keys identifying a paper. Used for history dedup,
    where the same paper may be referenced by arxiv id, DOI, or normalized
    title across different sources / history schemas."""
    keys: set[str] = set()
    url = paper.get("url", "") or ""
    title = paper.get("title", "") or ""
    explicit_id = str(paper.get("id", "") or "")
    explicit_doi = paper.get("doi", "") or ""

    arxiv = extract_arxiv_id(url) or extract_arxiv_id(explicit_id)
    if arxiv:
        keys.add(f"arxiv:{arxiv}")

    for candidate in (explicit_doi, url, explicit_id):
        doi = extract_doi(candidate)
        if doi:
            keys.add(f"doi:{doi}")
            break

    fallback_title = title or (explicit_id if not explicit_id.startswith(("http", "10.")) else "")
    norm = normalize_title(fallback_title)
    if norm:
        keys.add(f"title:{norm}")

    return keys


def dedup_key(paper: dict) -> str:
    """Single strongest key for in-memory merge dedup. Prefers arxiv > doi > title."""
    keys = paper_lookup_keys(paper)
    for prefix in ("arxiv:", "doi:", "title:"):
        for key in keys:
            if key.startswith(prefix):
                return key
    return f"title:{(paper.get('title') or '').strip().lower()}"


def apply_age_decay(papers: list[dict], target_date) -> None:
    """Reduce score for older papers so DBLP back-catalog cannot overpower
    today's arXiv. Mutates papers in place."""
    for paper in papers:
        date_str = paper.get("date", "") or ""
        if not date_str:
            continue
        try:
            pdate = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        age_days = (target_date - pdate).days
        if age_days <= 30:
            continue
        if age_days <= 180:
            factor = 0.75
        elif age_days <= 365:
            factor = 0.55
        else:
            factor = 0.35
        paper["score"] = int(paper["score"] * factor)


def select_with_quota(candidates: list[dict], top_n: int, dblp_max_ratio: float = 0.4) -> list[dict]:
    """Cap how many slots DBLP / venue scrapes can take, so today's arXiv
    is not crowded out by year-old conference papers."""
    dblp_max = max(1, int(top_n * dblp_max_ratio))
    arxiv = [p for p in candidates if p.get("source") == "arxiv"]
    # 先按分数排再截：candidates 是按 VENUE_SPECS 顺序插进来的，不排序的话名额全给了排在前面的会议
    others = sorted((p for p in candidates if p.get("source") != "arxiv"), key=lambda item: item["score"], reverse=True)
    others = others[:dblp_max]
    combined = arxiv + others
    combined.sort(key=lambda item: item["score"], reverse=True)
    return combined[:top_n]


def load_history() -> list[dict]:
    if HISTORY_PATH.exists():
        try:
            return json.loads(HISTORY_PATH.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return []


def load_fallback_ids(days: int = 7) -> set[str]:
    ids = set()
    today = datetime.now().date()
    for offset in range(1, days + 1):
        fpath = DAILYPAPERS_DIR / f"{(today - timedelta(days=offset)).isoformat()}-论文推荐.md"
        if not fpath.exists():
            continue
        try:
            text = fpath.read_text()
        except IOError:
            continue
        for match in re.finditer(r"arxiv\.org/abs/(\d{4}\.\d{4,5})", text):
            ids.add(match.group(1))
    return ids


def build_history_index(history: list[dict]) -> tuple[set[str], dict[str, str]]:
    """Build a set of all lookup keys present in history plus a key→date map.
    Tolerant of history rows that use title, DOI, or arxiv URL as the id."""
    keys: set[str] = set()
    key_dates: dict[str, str] = {}
    for item in history:
        raw_id = str(item.get("id", "") or "")
        item_keys = paper_lookup_keys(
            {
                "url": raw_id if raw_id.startswith("http") else "",
                "doi": raw_id if raw_id.startswith("10.") else "",
                "title": item.get("title", "") or (raw_id if not raw_id.startswith(("http", "10.")) else ""),
                "id": raw_id,
            }
        )
        paper_date = item.get("date", "") or ""
        for key in item_keys:
            keys.add(key)
            if paper_date and (key not in key_dates or paper_date < key_dates[key]):
                key_dates[key] = paper_date
    return keys, key_dates


def merge_and_dedup(primary_papers: list[dict], arxiv_papers: list[dict], target_date, days: int = 1, top_n: int = TOP_N) -> list[dict]:
    by_key = {}
    for paper in primary_papers + arxiv_papers:
        key = dedup_key(paper)
        if key not in by_key or paper["score"] > by_key[key]["score"]:
            by_key[key] = paper

    print(f"  Merged: {len(by_key)} unique papers", file=sys.stderr)

    apply_age_decay(list(by_key.values()), target_date)

    if days > 1:
        candidates = [paper for paper in by_key.values() if paper["score"] >= MIN_SCORE]
        top = select_with_quota(candidates, top_n)
        print(f"  Multi-day mode: {len(top)} papers", file=sys.stderr)
        return top

    history = load_history()
    history_keys, history_dates = build_history_index(history)

    if len(history) < 10:
        for paper_id in load_fallback_ids():
            history_keys.add(f"arxiv:{paper_id}")
            history_dates.setdefault(f"arxiv:{paper_id}", "unknown")

    deduped = {}
    removed = 0
    for key, paper in by_key.items():
        if paper_lookup_keys(paper) & history_keys:
            removed += 1
            continue
        deduped[key] = paper

    print(f"  After history dedup: {len(deduped)} (removed {removed})", file=sys.stderr)

    candidates = [paper for paper in deduped.values() if paper["score"] >= MIN_SCORE]
    top = select_with_quota(candidates, top_n)

    if len(top) < top_n and removed > 0:
        backfill = []
        for paper in by_key.values():
            paper_keys = paper_lookup_keys(paper)
            matched_keys = paper_keys & history_keys
            if not matched_keys or paper["score"] < MIN_SCORE:
                continue
            paper = dict(paper)
            paper["is_re_recommend"] = True
            paper["last_recommend_date"] = next(
                (history_dates.get(k, "unknown") for k in matched_keys),
                "unknown",
            )
            backfill.append(paper)
        backfill.sort(key=lambda item: item["score"], reverse=True)
        needed = top_n - len(top)
        if needed > 0 and backfill:
            top.extend(backfill[:needed])
            print(f"  Back-filled {min(needed, len(backfill))} from history", file=sys.stderr)

    print(f"  Final: {len(top)} papers", file=sys.stderr)
    return top


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--days", type=int, default=1, help="Number of days to fetch (default: 1)")
    args = parser.parse_args()

    target_date = (
        datetime.strptime(args.date, "%Y-%m-%d").date()
        if args.date
        else datetime.now().date()
    )
    days = max(1, args.days)
    start_date = target_date - timedelta(days=days - 1)
    top_n = TOP_N * days

    print(
        f"[fetch_and_score] {target_date}"
        + (f", days={days} [{start_date} ~ {target_date}], top_n={top_n}" if days > 1 else ""),
        file=sys.stderr,
    )

    primary_papers = fetch_dblp_papers(target_date)
    # 程序页总是抓：DBLP 收录要滞后几个月，刚开完的会只在程序页上；重复的论文在 merge_and_dedup 里按标题去重
    primary_papers.extend(fetch_conference_program_papers(target_date))

    arxiv_papers = fetch_arxiv_papers(start_date, target_date, days)

    if len(primary_papers) + len(arxiv_papers) < 20:
        semantic_scholar_papers = fetch_semantic_scholar_papers(target_date, days=days)
        primary_papers.extend(semantic_scholar_papers)

    top = merge_and_dedup(primary_papers, arxiv_papers, target_date, days=days, top_n=top_n)

    json.dump(top, sys.stdout, ensure_ascii=False, indent=2)
    print(file=sys.stdout)


if __name__ == "__main__":
    main()
