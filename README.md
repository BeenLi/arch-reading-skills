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

The agent interprets requests and writes reviews and long notes; Python scripts do the deterministic parts: fetching, scoring, de-duplication, Zotero lookups, path planning, index generation and text checks. How the pieces fit together (data flow, file ownership, templates, scoring rules, tests) is documented in [`ARCHITECTURE.md`](ARCHITECTURE.md) (in Chinese).

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

`skills/_shared` is not a skill: it holds the configuration, scripts and diagram rules the skills share. Every skill that uses it carries a generated copy in its own `_shared/` folder (`paper-reader`, `concept-notes` and `daily-papers` the whole folder, `repo-reader`, `book-reader` and `paper-to-zotero` only the files they use), so each skill works on its own whichever way it is installed.

### Extra dependencies of `verilog-diagram`

`gpt-image-bridge` is part of this repository, so any of the three methods above installs it along with everything else. It is optional: it only provides layout sketches for `verilog-diagram`, which skips that step when it is missing.

What is not in this repository is the third-party [drawio-skill](https://github.com/Agents365-ai/drawio-skill). The skills CLI and the plugin install only this repository's skills, so install it once yourself (it is the same line as in the macOS dependencies above; skip it if you ran that):

```bash
npx skills add Agents365-ai/drawio-skill -g -a claude-code -y
```

To install only the diagram skills instead of the whole repository, pick them with `--skill`:

```bash
npx skills add BeenLi/arch-reading-skills -g -a claude-code --skill verilog-diagram gpt-image-bridge -y
```

| View | Needs |
|---|---|
| Architecture and FSM diagrams (`.drawio`) | This skill only |
| Block and control diagrams, `validate.py` checks | drawio-skill plus `yosys`, `sv2v` (SystemVerilog) and Graphviz: `brew install yosys sv2v graphviz` |
| PNG / SVG export | draw.io desktop (`brew install --cask drawio`); on a Linux server without root, `skills/verilog-diagram/scripts/install-drawio-linux.sh` |
| Layout sketches | `gpt-image-bridge` (installed with the repository) and a logged-in [`codex` CLI](https://github.com/openai/codex) |

Before drawing, the skill looks for drawio-skill in `$DRAWIO_SKILL_DIR`, `~/.claude/skills/drawio-skill`, `~/.agents/skills/drawio-skill` and the plugin cache, in that order. If it is missing, the skill shows the install command above and runs it only after you agree; without it, it draws only the views that do not need it.

### Setting up the Obsidian vault

An Obsidian vault is an ordinary local folder: notes are the Markdown files in it, and Obsidian keeps that vault's settings and plugins in a hidden `.obsidian/` folder at its root (see the official [How Obsidian stores data](https://obsidian.md/help/data-storage)). The skills only write Markdown and images into this folder; Obsidian does not need to be running.

**1. Create or open a vault** (official steps: [Manage vaults](https://obsidian.md/help/manage-vaults))

- New vault: open Obsidian → the vault icon at the bottom left → **Manage Vaults…** → **Create** next to **Create new vault** → enter a name, **Browse** to a location → **Create**.
- Existing folder of notes: in the same menu choose **Open folder as vault** → **Open**, and select the folder.

**2. Choose where it lives**

- One computer only: anywhere under your home folder, for example `~/ObsidianVault` (the path in the default configuration).
- Syncing between a Mac and an iPhone / iPad with iCloud: when creating the vault, pick **iCloud Drive → Obsidian** in the file picker. The vault then sits in `iCloud Drive/Obsidian/<vault name>`, which is `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/<vault name>` in a terminal. In Finder, choose "Keep Downloaded" for it so iCloud does not offload the files. Other options (Obsidian Sync, Git and so on) are in [Sync your notes across devices](https://obsidian.md/help/sync-notes).
- Do not create a vault inside another vault (internal links resolve only within one vault), or inside a system folder.

**3. Create the folders the skills use**

The folder that `paths.obsidian_vault` points to (see [Configuration](#configuration)) needs `DailyPapers/` and `PaperNotes/`. It can be the vault root or a subfolder of the vault:

```bash
# a. directly in the vault root
VAULT=~/ObsidianVault
mkdir -p "$VAULT/DailyPapers" "$VAULT/PaperNotes/_concepts" "$VAULT/PaperNotes/_inbox"
```

```bash
# b. grouped in a subfolder such as 001-input/PaperRead; set paths.obsidian_vault to that subfolder
VAULT=~/ObsidianVault/001-input/PaperRead
mkdir -p "$VAULT/DailyPapers" "$VAULT/PaperNotes/_concepts" "$VAULT/PaperNotes/_inbox"
```

The eight category folders under `_concepts/` and the `_index_*.md` index pages are created the first time a skill writes there. `repo-reader` writes guides to `repo_reader.guide_dir` instead; create that folder when you need it.

**4. Suggested Obsidian settings**

- Settings → Files and links → Default location for new attachments: choose "In subfolder under current folder" and enter `00_assets`. Generated notes keep their images in a `00_assets/` folder next to the note, so images you paste by hand end up in the same place.
- The [Dataview](https://github.com/blacksmithgu/obsidian-dataview) community plugin is optional; install it if you want query tables over the frontmatter (`venue`, `year`, `tags`, `zotero_collection`).
- If you back up the vault with Git, add `.obsidian/workspace.json` and `.obsidian/workspaces.json` to `.gitignore`, as the official docs suggest. `automation.git_commit` only works when the vault is a git repository.

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
| `paper_to_zotero.collection_root` | Zotero collection under which `paper-to-zotero` picks a leaf; default `Computer Architecture`; an empty string means the whole library. If the library has no such collection, the skill stops and tells you why and how to change it |
| `paper_to_zotero.collection_hints` | Notes on each leaf: the key is the path below the root (`Memory & Storage / Storage Systems`), the value says which papers go there. The defaults describe 18 architecture leaves you can copy as a starting taxonomy in Zotero; to file papers your own way, write your own in your config file. Hints merge key by key and appear only next to leaves that exist in your library, so defaults that do not match never show up |

Which skill and script reads which setting: [`ARCHITECTURE.md` §5](ARCHITECTURE.md#5-配置).

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

By default only the first two steps run, so one recommendation doesn't produce a pile of long notes. `跑一下论文抓取 / 点评 / 笔记` runs a single step. Scoring rules, the review triage and the intermediate files are in [`ARCHITECTURE.md` §2](ARCHITECTURE.md#2-每日推荐daily-papers).

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

- Notes follow [`skills/paper-reader/assets/paper-note-template.md`](skills/paper-reader/assets/paper-note-template.md) exactly; section structure, hard writing rules and post-write checks are in [`ARCHITECTURE.md` §4](ARCHITECTURE.md#4-论文笔记模板paper-reader).
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

The scanner ignores `_concepts/`, `_inbox/`, `_index_*.md` and links between paper notes. File ownership, the five modes, filter rules and the eight categories are in [`ARCHITECTURE.md` §3](ARCHITECTURE.md#3-概念库concept-notes).

### Adding papers to Zotero — `paper-to-zotero`

```text
把 https://arxiv.org/abs/2405.10170 加到 Zotero
```

Fetches metadata (Crossref / arXiv), checks for duplicates, picks a leaf collection from the abstract (under `paper_to_zotero.collection_root`, guided by `collection_hints`), downloads the PDF (arXiv → open access → publisher), and creates the item with the PDF attached through the Zotero 10 local API. With no PDF it stops before creating anything. Afterwards it asks once whether to read the paper with `paper-reader`.

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

New files follow this split; `tests/test_repo_layout.py` checks that `.py` files live only under `scripts/` and that every `python3 …py` path in the Markdown resolves. Which skills carry which `_shared` files: [`ARCHITECTURE.md` §6.1](ARCHITECTURE.md#61-_shared-怎么分发).

## Adding a skill

Take a new `foo-reader` as the example. The skills CLI and the plugin both discover `skills/*/SKILL.md` on their own, so there is no list to register it in, but follow the conventions below or the skill will be missing files when installed on its own.

**1. Create the folder and `SKILL.md`**

```text
skills/foo-reader/
├── SKILL.md          # required
├── scripts/          # executable code, called from SKILL.md relative to the skill folder
├── references/       # rules and guides the agent reads into context
└── assets/           # templates filled in or copied into the output
```

`SKILL.md` starts with YAML frontmatter:

```markdown
---
name: foo-reader
description: One or two sentences on what it does, then the phrases users say, such as "read this XXX" or "summarise XXX".
---

# foo-reader

Body: the steps the agent follows, which scripts it calls, what it produces, and when it stops to ask the user.
```

- `name` matches the folder name, in lowercase letters and hyphens.
- `description` decides when Claude invokes the skill on its own: purpose first, then trigger phrases, under about 1,500 characters (Claude Code truncates the rest in its skill listing).
- The full field reference is the official Claude Code page [Extend Claude with skills](https://code.claude.com/docs/en/skills). Inside Claude Code, `skill-creator` or `superpowers:writing-skills` can draft and test a skill with you.

**2. Make it work when installed on its own**

`npx skills add` copies only the skill's own folder, so:

- Do not use paths into sibling folders such as `../_shared/…` or `../concept-notes/…`, and do not commit symlinks.
- To use scripts or settings from `skills/_shared`, add the skill to `TARGETS` in [`scripts/sync_shared.py`](scripts/sync_shared.py) (`None` for the whole folder, or a list of files) and run `python3 scripts/sync_shared.py` to generate `skills/foo-reader/_shared/`. In scripts, copy `_find_shared_scripts()` from `skills/paper-to-zotero/scripts/zotero_add.py`: it uses the source inside the repository and the copy when installed on its own.
- Do not hard-code personal settings such as paths or collection names. Add a generic default to `skills/_shared/user-config.json` and to `DEFAULT_CONFIG` in `user_config.py`, plus a getter; your own values go in `~/.config/arch-reading-skills/user-config.json`.
- If the skill depends on another skill or a command-line tool outside this repository, start `SKILL.md` with a check: when it is missing, show the install command, install only after the user agrees, and otherwise skip the steps that need it (see how `verilog-diagram` handles drawio-skill).
- A skill imported from elsewhere keeps its `LICENSE`, and the README names its source (see `gpt-image-bridge` and `book-reader`).

**3. Test it**

Put tests for the deterministic parts of its scripts in `tests/test_foo_reader.py`. Tests that need configuration point `ARCH_READING_CONFIG` at a temporary file instead of reading your own. Before committing:

```bash
python3 scripts/sync_shared.py --check
python3 -m pytest tests/ -q
```

`tests/test_repo_layout.py` covers the new skill automatically: `.py` files may live only under `scripts/`, and every `python3 …py` path in its Markdown must resolve.

**4. Register it in the docs and on your machine**

- Both READMEs: the skill table at the top, a short section under "Workflows" (trigger phrases and what it does), and a line under "Repository layout".
- [`ARCHITECTURE.md`](ARCHITECTURE.md): the skill table in [§1](ARCHITECTURE.md#1-总览) and the `_shared` paragraph in [§6.1](ARCHITECTURE.md#61-_shared-怎么分发). It is hard-linked into the author's vault ([appendix](ARCHITECTURE.md#附录obsidian-硬链接)), so edit it in place rather than replacing the file.
- Add the name to the `for d in …` list in install method 3, then symlink it locally; a new Claude Code session picks it up:

  ```bash
  ln -sfn "$PWD/skills/foo-reader" ~/.claude/skills/foo-reader
  ```

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

What each test file covers is listed in [`ARCHITECTURE.md` §7](ARCHITECTURE.md#7-测试).

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
