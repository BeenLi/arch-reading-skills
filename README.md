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
| `paper-to-zotero` | Adds a paper (title, DOI, arXiv ID or link) to Zotero with its PDF, in the right leaf collection, through the Zotero 10 local API |
| `concept-notes` | Sole owner of the concept library: creates / rewrites concept notes and refreshes the paper and concept index pages |
| `book-reader` | Reads a whole book and writes reading notes with a mind map of the book |
| `kepu-research-doc` | Writes an illustrated Chinese explainer / survey document that sorts a confusing topic into a few independent axes |
| `repo-reader` | Reads a code repository and writes an architecture and usage guide whose claims trace back to source files |
| `verilog-diagram` | Turns Verilog / SystemVerilog (or a paper or description) into editable draw.io architecture, block, FSM and control diagrams |
| `gpt-image-bridge` | Generates images with GPT Image through the `codex` CLI and a ChatGPT subscription; asks before every image |

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
- `poppler` (`pdftotext`, `pdfimages`): affiliation extraction in `daily-papers` and PDF figure extraction
- Optional, for self-drawn diagrams in notes (see `skills/_shared/references/diagram-rules.md`):
  - [diagram-design](https://github.com/cathrynlavery/diagram-design) plus Playwright: the default route, exported as PNG
  - draw.io desktop and [drawio-skill](https://github.com/Agents365-ai/drawio-skill): sequence, Gantt and pipeline diagrams; also needed by `verilog-diagram`
  - `mmdc` (mermaid-cli): renders the Mermaid fallback so it can be checked by eye

On macOS:

```bash
brew install poppler
npm install -g @mermaid-js/mermaid-cli
python3 -m pip install --user playwright && python3 -m playwright install chromium
npx skills add cathrynlavery/diagram-design -g -a claude-code
npx skills add Agents365-ai/drawio-skill -g -a claude-code
brew install --cask drawio
```

Install the skills one of three ways:

```bash
# 1. skills CLI: copies each skill into ~/.claude/skills; update later with `npx skills update -g`
npx skills add BeenLi/arch-reading-skills -g -a claude-code
```

```text
# 2. Claude Code plugin: run inside Claude Code; skill names get the plugin prefix (arch-reading:paper-reader)
/plugin marketplace add BeenLi/arch-reading-skills
/plugin install arch-reading@arch-reading-skills
```

```bash
# 3. git clone + symlinks, for development: changes in the repo take effect immediately
git clone https://github.com/BeenLi/arch-reading-skills.git && cd arch-reading-skills
mkdir -p ~/.claude/skills
for d in paper-reader concept-notes daily-papers paper-to-zotero book-reader repo-reader kepu-research-doc verilog-diagram gpt-image-bridge; do
  ln -sfn "$PWD/skills/$d" "$HOME/.claude/skills/$d"
done
```

`verilog-diagram` needs the third-party [drawio-skill](https://github.com/Agents365-ai/drawio-skill), which the skills CLI does not install for you; `gpt-image-bridge` is optional and only used for layout sketches. To install them together:

```bash
npx skills add Agents365-ai/drawio-skill -g -a claude-code -y && npx skills add BeenLi/arch-reading-skills -g -a claude-code --skill verilog-diagram gpt-image-bridge -y
```

Block and control diagrams also need `yosys`, `sv2v` and Graphviz. The skill checks for drawio-skill before drawing and offers the install command if it is missing.

`skills/_shared` is not a skill: it holds the configuration, scripts and diagram rules the skills share. Every skill that uses it carries a generated copy in its own `_shared/` folder (`paper-reader`, `concept-notes` and `daily-papers` the whole folder, `repo-reader` and `book-reader` only the files they use), so each skill works on its own whichever way it is installed.

Create the Obsidian folders:

```bash
VAULT=~/ObsidianVault
mkdir -p "$VAULT/DailyPapers" "$VAULT/PaperNotes/_concepts" "$VAULT/PaperNotes/_inbox"
```

### Configuration

All personal settings live in **one file**, `~/.config/arch-reading-skills/user-config.json`. It sits outside the skill folders, so `npx skills update`, a plugin update or `git pull` never overwrites it. Write only what differs from the defaults in [`skills/_shared/user-config.json`](skills/_shared/user-config.json):

```bash
mkdir -p ~/.config/arch-reading-skills
cat > ~/.config/arch-reading-skills/user-config.json <<'EOF'
{
  "paths": {
    "obsidian_vault": "~/ObsidianVault",
    "zotero_db": "~/Zotero/zotero.sqlite",
    "zotero_storage": "~/Zotero/storage"
  },
  "repo_reader": {
    "guide_dir": "~/ObsidianVault/002-notes/001 使用指南"
  }
}
EOF
```

How it is read:

- Defaults come first, then your file on top. Nested objects merge key by key, so `{"daily_papers": {"min_score": 4}}` changes only that value. **Lists are replaced as a whole**: to add a keyword, copy the default `keywords` list into your file and extend it.
- `ARCH_READING_CONFIG=/path/to/other.json` uses that file instead of the default location, for example a second vault or an experiment with other keywords. When it is set, the default location is not read even if the file it names is missing (the tests rely on this).
- Changes take effect on the next run. To see the effective value of a setting:

  ```bash
  cd skills/_shared/scripts && python3 -c "import user_config as u; print(u.paper_notes_dir(), u.daily_papers_config()['min_score'])"
  ```

| Setting | Meaning |
|---|---|
| `paths.obsidian_vault` | Folder that holds `PaperNotes/` and `DailyPapers/` (it can be a subfolder of the vault, such as `…/001-input/PaperRead`) |
| `paths.paper_notes_folder` / `daily_papers_folder` / `concepts_folder` | Folder names under it, default `PaperNotes` / `DailyPapers` / `_concepts` |
| `paths.zotero_db` / `zotero_storage` | Zotero database and attachment folder |
| `paths.zotero_base_attachment_path` | Base folder for linked attachments stored as `attachments:…` (ZotMoov and similar); optional |
| `daily_papers.keywords` | Main scoring keywords (+3 in the title, +1 in the abstract) |
| `daily_papers.negative_keywords` | A title hit excludes the paper (`-999`); kept to topics unrelated to architecture or LLM systems |
| `daily_papers.domain_boost_keywords` | Architecture relevance words, scored by how many appear |
| `daily_papers.focus_phrases` | Core-topic phrases (multicore, cache / memory hierarchy, heterogeneous computing…), +1 each |
| `daily_papers.venue_rank_scores` | Points by CCF tier, default A / B / C = 3 / 2 / 1; only added when the topic matches |
| `daily_papers.arxiv_categories` / `min_score` / `top_n` | arXiv categories, minimum score, daily candidate cap |
| `automation.*` | Whether to refresh index pages, commit and push automatically; `git_push` only applies when `git_commit=true` |
| `mocs.filename_prefix` | Index page file-name prefix, usually `_index_` |
| `repo_reader.guide_dir` | Vault folder where `repo-reader` writes architecture guides |

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

### Adding papers to Zotero — `paper-to-zotero`

```text
把 https://arxiv.org/abs/2405.10170 加到 Zotero
```

Fetches metadata (Crossref / arXiv), checks for duplicates, picks a leaf collection under Computer Architecture from the abstract, downloads the PDF (arXiv → open access → publisher), and creates the item with the PDF attached through the Zotero 10 local API. With no PDF it stops before creating anything. Afterwards it asks once whether to read the paper with `paper-reader`.

### Explainer documents — `kepu-research-doc`

```text
写一份科普调研文档：DPU 的来由与软硬件架构
```

Turns a topic and reference material into a Chinese Markdown + PDF document: conclusion and axes first, a glossary, one section per axis, "what each thing was originally built for", and how they combine; plus a cover image, a short promo blurb and a private notes file kept apart from the public text. The cover is generated by `scripts/make_cover.py` + `scripts/export_cover.py` (Playwright + Chromium); the style spec is `references/COVER-STYLE.md` and samples are in `assets/`.

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
- Output: written into the repository and hard-linked into the vault's guide folder when the repository already has an `ARCHITECTURE.md` or you ask for it; otherwise only into the vault. The folder comes from `repo_reader.guide_dir` in your config file (see [Configuration](#configuration))

### Hardware diagrams — `verilog-diagram`

```text
把这个 module 画成架构图 rtl/dcache_pipe.v     # architecture diagram, paper-figure style
画出 load_pipe.v 的状态机                      # FSM diagram
根据这篇论文画架构图                           # from a paper or a description
```

Four views: a paper-style architecture diagram (default; the agent reads the code and writes a layout description, a script draws it), a gate-level block diagram from the Yosys netlist, an FSM diagram, and a control-structure diagram. Output is an editable `.drawio` file, plus PNG / SVG when a draw.io exporter is available; on a headless Linux server without root, `skills/verilog-diagram/scripts/install-drawio-linux.sh` sets one up.

### Image generation — `gpt-image-bridge`

```text
画一张这个系统的示意图
```

Calls GPT Image through the [`codex` CLI](https://github.com/openai/codex) with your ChatGPT login, no API key. Every image uses ChatGPT quota and takes minutes, so the agent lists the planned images and waits for a yes first. `verilog-diagram` uses it, when installed, for an optional layout sketch. Imported from [BeenLi/gpt-image-bridge](https://github.com/BeenLi/gpt-image-bridge), a fork of [oakplank/gpt-image-bridge](https://github.com/oakplank/gpt-image-bridge) (MIT).

## Repository layout

```text
skills/
├── daily-papers/          # Daily recommendations: fetch → review → optional notes; scripts/ fetch, score, enrich, localise images
├── paper-to-zotero/       # Paper → Zotero item with PDF and collection; scripts/zotero_add.py (Zotero 10 local API)
├── paper-reader/          # Single-paper reading and Zotero integration; scripts/ references/ assets/
├── concept-notes/         # Owns concepts: assets/ template; references/ classification; scripts/ scan, rewrite, length check; index refresh
├── book-reader/           # Whole-book notes and mind maps (MIT, Tao Jiang)
├── kepu-research-doc/     # Chinese explainer / survey documents with figures, cover and promo blurb; scripts/ cover + diagram generators and PNG export; references/ cover spec; assets/ samples
├── repo-reader/           # Repository → architecture and usage guide; scripts/ facts and checker; references/ 12-section contract
├── verilog-diagram/       # Verilog / papers → draw.io diagrams; scripts/ generators, exporter, Linux draw.io installer; examples/
├── gpt-image-bridge/      # GPT Image through the codex CLI; bin/ wrapper script (MIT, oakplank)
└── _shared/               # Shared config; scripts/ index generation, escape checks, venue labels, CCF ranks; references/ diagram rules
scripts/sync_shared.py     # Copies skills/_shared into the skills that use it
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

`skills/_shared` is the only source; `skills/<name>/_shared/` are generated copies that are committed but never edited by hand. Scripts look for the source first and fall back to the copy, so edits to `skills/_shared` take effect at once in a clone. Regenerate the copies before committing; the pre-commit hook and CI run the check:

```bash
git config core.hooksPath .githooks   # once per clone
python3 scripts/sync_shared.py         # regenerate the copies
python3 scripts/sync_shared.py --check # check only
```

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
