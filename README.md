# arch-reading-skills

**English** | [简体中文](README.zh-CN.md)

Claude Code skills for computer-architecture (multicore, cache and memory hierarchy, heterogeneous computing, interconnects) and LLM-systems research. The daily-recommendation defaults work out of the box: architecture first, LLM systems second. Together they connect daily paper discovery, close reading of single papers, a concept library, whole-book reading, code-repository reading, your Zotero library and your Obsidian vault into one local workflow.

https://github.com/user-attachments/assets/1abe137d-5dd1-46b5-b766-40f239380d6c

<p align="center"><sub>51-second demo of <code>daily-papers</code>: fetch → score (keywords + CCF tiers) → review, using numbers and picks from a real 7-day run. Made with Remotion.
⬇ <a href="https://github.com/BeenLi/arch-reading-skills/raw/main/media/daily-papers-demo.mp4">Download mp4</a></sub></p>

| Skill | What it does |
|---|---|
| `daily-papers` | Daily paper recommendations: fetch → review → optional batch close reading |
| `paper-reader` | Reads one paper, writes an Obsidian note from a template, and creates notes for the new concepts it meets |
| `concept-notes` | Sole owner of the concept library: creates / rewrites concept notes and refreshes the paper and concept index pages |
| `book-reader` | Reads a whole book and writes reading notes with a mind map of the book |
| `repo-reader` | Reads a code repository and writes an architecture and usage guide whose claims trace back to source files |
| `verilog-diagram` | Turns Verilog / SystemVerilog (or a paper or description) into editable draw.io architecture, block, FSM and control diagrams |

The agent interprets requests and writes reviews and long notes; Python scripts do the deterministic parts: fetching, scoring, de-duplication, Zotero lookups, path planning, index generation and text checks.

Typical Obsidian output:

```text
ObsidianVault/
├── DailyPapers/YYYY-MM-DD-论文推荐.md
└── PaperNotes/
    ├── Research Topics/.../{MethodName}.md
    ├── _concepts/{concept_type}/{ConceptName}.md
    ├── _inbox/{MethodName}.md
    └── _index_*.md
```

## Installation and configuration

Requirements:

- Claude Code
- Python 3.10+
- Obsidian
- Zotero, optional but recommended (writes go through the Zotero 10 local API)
- `poppler` / `poppler-utils`, for `pdftotext` and `pdfimages`
- `mmdc`, optional, to validate Mermaid diagrams

Symlink the skills into Claude Code's skills directory so changes in the repo take effect immediately:

```bash
mkdir -p ~/.claude/skills
for d in paper-reader concept-notes daily-papers book-reader repo-reader verilog-diagram _shared; do
  ln -sfn "$PWD/skills/$d" "$HOME/.claude/skills/$d"
done
```

`verilog-diagram` also needs the third-party [drawio-skill](https://github.com/Agents365-ai/drawio-skill) (`npx skills add Agents365-ai/drawio-skill -g -a claude-code`), plus `yosys`, `sv2v` and Graphviz for block and control diagrams.

`_shared` is not a skill: it holds the configuration, scripts and diagram rules the skills share. The `../_shared/…` paths in each SKILL.md assume it sits next to the other skills.

Create the Obsidian folders:

```bash
VAULT=~/ObsidianVault
mkdir -p "$VAULT/DailyPapers" "$VAULT/PaperNotes/_concepts" "$VAULT/PaperNotes/_inbox"
```

Shared settings live in `skills/_shared/user-config.json`. Put personal paths and keyword overrides in `user-config.local.json` next to it (git-ignored). Load order: defaults in `user_config.py` → `user-config.json` → `user-config.local.json`.

| Setting | Meaning |
|---|---|
| `paths.*` | Obsidian vault, paper-notes folder, daily-papers folder, concept folder, Zotero DB / storage |
| `daily_papers.keywords` | Main scoring keywords (+3 in the title, +1 in the abstract) |
| `daily_papers.negative_keywords` | A title hit excludes the paper (`-999`); kept to topics unrelated to architecture or LLM systems |
| `daily_papers.domain_boost_keywords` | Architecture relevance words, scored by how many appear |
| `daily_papers.focus_phrases` | Core-topic phrases (multicore, cache / memory hierarchy, heterogeneous computing…), +1 each |
| `daily_papers.venue_rank_scores` | Points by CCF tier, default A / B / C = 3 / 2 / 1; only added when the topic matches |
| `daily_papers.arxiv_categories` / `min_score` / `top_n` | arXiv categories, minimum score, daily candidate cap |
| `automation.*` | Whether to refresh index pages, commit and push automatically; `git_push` only applies when `git_commit=true` |
| `mocs.filename_prefix` | Index page file-name prefix, usually `_index_` |

## Workflows

Each section lists what to say to Claude Code, then what happens. The trigger phrases are Chinese; `paper-reader` also responds to English requests such as "read this paper".

### Daily paper recommendations — `daily-papers`

```text
今日论文推荐          # today's recommendations
过去3天论文推荐        # last 3 days
过去一周论文推荐       # last week
跑一下论文笔记         # batch notes for the top picks
```

One skill runs three steps:

1. Fetch: DBLP, conference program pages and arXiv, with Semantic Scholar as a fallback; score by keywords and CCF venue tier, drop already-recommended papers, enrich, and write `/tmp/daily_papers_enriched.json`.
2. Review: write `{DailyPapers}/YYYY-MM-DD-论文推荐.md` (1–2 top picks, up to 3 alternates) and update `.history.json`.
3. Notes (optional): call `paper-reader` for each top pick and link the notes back into the recommendation file.

By default only the first two steps run, so one recommendation doesn't produce a pile of long notes. `跑一下论文抓取 / 点评 / 笔记` runs a single step.

### Reading papers — `paper-reader`

```text
读一下这篇论文 https://arxiv.org/abs/2509.24527          # read this paper
读一下这篇论文 ~/Downloads/paper.pdf
快速看一下这篇论文 https://arxiv.org/abs/2509.24527      # quick summary
批判性分析这篇论文 ~/Downloads/paper.pdf                  # critical analysis
读一下 Zotero item 2487
读一下 Zotero 里的 vLLM                                   # search Zotero
批量读一下 Zotero 里 Link & Fabric Integration 分类下的论文  # a whole collection
```

Inputs: local PDF, arXiv / DOI / web links, a Zotero item, a Zotero search, or a Zotero collection (the agent calls this skill once per paper).

- Notes follow [`skills/paper-reader/assets/paper-note-template.md`](skills/paper-reader/assets/paper-note-template.md) exactly.
- File names use the main method or system name, `{MethodName}.md`. Papers in a Zotero collection are saved under `{PaperNotes}/{collection_path}/`, others under `{PaperNotes}/_inbox/`.
- `zotero_item_id`, `doi` and `arxiv_id` go into the frontmatter for exact de-duplication; batch mode skips papers that already have notes.
- After the note is written, `concept-notes` mode E creates notes for the paper's new concepts, then `check_note_links.py` checks the links of the paper note and the new concepts together.
- Zotero is read-only by default. Moving, adding or removing collections, fixing fields or deleting items happens only when you ask, through the Zotero local API.

### Concept library and index pages — `concept-notes`

```text
生成概念 KV Cache      # create a concept note
补全缺失的概念         # fill in missing concepts
重新生成概念笔记       # rewrite concept notes with the current template
检查概念长度           # check concept length
更新索引               # refresh index pages
```

Concept rules and scripts live only here: the template in [`skills/concept-notes/assets/concept-note-template.md`](skills/concept-notes/assets/concept-note-template.md), the classification rules in [`skills/concept-notes/references/concept-categories.md`](skills/concept-notes/references/concept-categories.md), and the scan / rewrite / length-check scripts in `skills/concept-notes/scripts/`.

Concept notes live in `{PaperNotes}/_concepts/`, grouped by what the concept is, not by research field:

```text
data-structure / algorithm / mechanism / architecture
hardware / software-abstraction / metric / theory-model
```

You can also run the scripts directly:

```bash
python3 skills/concept-notes/scripts/scan_missing_concepts.py --with-seed --dry-run
python3 skills/concept-notes/scripts/check_concept_length.py "<concept note>"
python3 skills/_shared/scripts/generate_concept_mocs.py
python3 skills/_shared/scripts/generate_paper_mocs.py
```

The scanner ignores `_concepts/`, `_inbox/`, `_index_*.md` and links between paper notes.

### Reading books — `book-reader`

```text
帮我读这本书 ~/Downloads/book.epub    # read this book
```

Extracts PDF / EPUB / MOBI / TXT by page or chapter, distils knowledge points in batches, and writes reading notes with a mind map of the whole book.

### Reading code repositories — `repo-reader`

```text
读一下这个仓库 https://github.com/vllm-project/vllm     # read this repository
给 ~/hardware-project/tiny-gpu 写架构和使用文档          # write an architecture and usage guide
```

Static source analysis only (it never runs the target repository's scripts, tests or builds). It writes a fixed 12-section architecture and usage guide in which every claim traces back to a source file.

- Contract: [`skills/repo-reader/references/doc-format.md`](skills/repo-reader/references/doc-format.md); checker: `python3 skills/repo-reader/scripts/check_doc.py <draft> --name <Name>`
- Raw facts: `python3 skills/repo-reader/scripts/repo_facts.py <repo>` (remote, HEAD, directory tree, entry-point candidates, README commands, config files)
- Output: written into the repository and hard-linked into the vault's guide folder when the repository already has an `ARCHITECTURE.md` or you ask for it; otherwise only into the vault. The folder comes from `guide_dir` in `skills/repo-reader/config.json` (copy it from `config.example.json`; not committed)

### Hardware diagrams — `verilog-diagram`

```text
把这个 module 画成架构图 rtl/dcache_pipe.v     # architecture diagram, paper-figure style
画出 load_pipe.v 的状态机                      # FSM diagram
根据这篇论文画架构图                           # from a paper or a description
```

Four views: a paper-style architecture diagram (default; the agent reads the code and writes a layout description, a script draws it), a gate-level block diagram from the Yosys netlist, an FSM diagram, and a control-structure diagram. Output is an editable `.drawio` file, plus PNG / SVG when a draw.io exporter is available; on a headless Linux server without root, `skills/verilog-diagram/scripts/install-drawio-linux.sh` sets one up.

## Repository layout

```text
skills/
├── daily-papers/          # Daily recommendations: fetch → review → optional notes; scripts/ fetch, score, enrich, localise images
├── paper-reader/          # Single-paper reading and Zotero integration; scripts/ references/ assets/
├── concept-notes/         # Owns concepts: assets/ template; references/ classification; scripts/ scan, rewrite, length check; index refresh
├── book-reader/           # Whole-book notes and mind maps (MIT, Tao Jiang)
├── repo-reader/           # Repository → architecture and usage guide; scripts/ facts and checker; references/ 12-section contract
├── verilog-diagram/       # Verilog / papers → draw.io diagrams; scripts/ generators, exporter, Linux draw.io installer; examples/
└── _shared/               # Shared config; scripts/ index generation, escape checks, venue labels, CCF ranks; references/ diagram rules
```

### Directory convention

Each skill splits its files into three folders by role:

| Folder | Holds | Test |
|---|---|---|
| `scripts/` | Executable code | Something you run with `python3 …` |
| `references/` | Rules, guides and classifications the agent reads into context | Changes how the agent works |
| `assets/` | Templates filled in or copied into the output | Appears in what gets generated |

New files follow this split; `tests/test_repo_layout.py` checks that `.py` files live only under `scripts/` and that every `python3 …py` path in the Markdown resolves.

## Development

```bash
python3 -m pytest tests/ -q
python3 skills/daily-papers/scripts/fetch_and_score.py > /tmp/daily_papers_top30.json
cat /tmp/daily_papers_top30.json | python3 skills/daily-papers/scripts/enrich_papers.py /tmp/daily_papers_enriched.json
```

Zotero helper compatibility:

- New docs and scripts use `zotero_helper.py resolve ...` and `zotero_helper.py note-path ...`
- The old `papers`, `search`, `info` and `find-collection` commands still work and print a deprecation warning; they will be removed in a later cleanup

## Notes

- De-duplication prefers `zotero_item_id`, `doi` and `arxiv_id`, then falls back to normalised title / method name.
- Daily recommendations and PDF / arXiv reading work without Zotero; Zotero adds local search, PDF lookup and collection paths.
- `git_commit` and `git_push` are off by default.
- AI-generated recommendations, reviews and notes can contain factual errors or omissions; use them as reading aids, not as a substitute for research judgement.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
