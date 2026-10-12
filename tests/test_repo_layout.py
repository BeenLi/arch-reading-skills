import importlib.util
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = REPO_ROOT / "skills"
SCRIPT_REF = re.compile(r"python3\s+(\S+\.py)")
RULE_REF = re.compile(r"_shared/(?:mermaid|diagram)-rules\.md")  # 正确路径是 _shared/references/…，不会命中


def markdown_files():
    yield from SKILLS.rglob("*.md")
    yield REPO_ROOT / "README.md"
    yield REPO_ROOT / "ARCHITECTURE.md"


def resolve_script_ref(md_path: Path, ref: str):
    """Map a `python3 <ref>` mention to a repo path; None = not ours, skip."""
    ref = ref.strip("\"'")
    if "$" in ref:  # "$DRAWIO/scripts/validate.py" 这类仓库外路径
        return None
    if ref.startswith("skills/"):
        return REPO_ROOT / ref
    for prefix in ("~/.claude/skills/", "~/.codex/skills/"):
        if ref.startswith(prefix):
            rel = ref[len(prefix):]
            return SKILLS / rel if (SKILLS / rel.split("/", 1)[0]).exists() else None
    if md_path.is_relative_to(SKILLS):
        skill_root = SKILLS / md_path.relative_to(SKILLS).parts[0]
        return (skill_root / ref).resolve()
    return (REPO_ROOT / ref).resolve()


def load_module_from_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RepoLayoutTests(unittest.TestCase):
    def test_shared_scripts_live_in_scripts_dir(self):
        self.assertEqual(sorted((SKILLS / "_shared").glob("*.py")), [])
        self.assertTrue((SKILLS / "_shared" / "scripts" / "user_config.py").exists())
        self.assertTrue((SKILLS / "_shared" / "scripts" / "md_escape_check.py").exists())
        self.assertTrue((SKILLS / "_shared" / "references" / "mermaid-rules.md").exists())
        self.assertTrue((SKILLS / "_shared" / "user-config.json").exists())

    def test_markdown_script_paths_resolve(self):
        offenders = []
        for md in markdown_files():
            for ref in SCRIPT_REF.findall(md.read_text(encoding="utf-8")):
                target = resolve_script_ref(md, ref)
                if target is not None and not target.exists():
                    offenders.append(f"{md.relative_to(REPO_ROOT)} -> {ref}")
        self.assertEqual(offenders, [])

    def test_rule_files_referenced_under_references_dir(self):
        offenders = [
            f"{md.relative_to(REPO_ROOT)}:{m.group(0)}"
            for md in markdown_files()
            for m in RULE_REF.finditer(md.read_text(encoding="utf-8"))
        ]
        self.assertEqual(offenders, [])

    def test_user_config_reads_json_one_level_above_scripts_dir(self):
        """user_config.py lives in _shared/scripts/ and must read _shared/user-config.json, not a file beside itself."""
        with tempfile.TemporaryDirectory() as tmp:
            shared = Path(tmp) / "_shared"
            (shared / "scripts").mkdir(parents=True)
            shutil.copy(SKILLS / "_shared" / "scripts" / "user_config.py", shared / "scripts" / "user_config.py")
            (shared / "user-config.json").write_text(
                json.dumps({"daily_papers": {"keywords": ["sentinel-keyword-from-json"]}}), encoding="utf-8"
            )
            module = load_module_from_path("user_config_under_test", shared / "scripts" / "user_config.py")

            keywords = module.load_user_config()["daily_papers"]["keywords"]

        self.assertIn("sentinel-keyword-from-json", keywords)

    def test_paper_reader_layout(self):
        root = SKILLS / "paper-reader"
        self.assertEqual(sorted(root.glob("*.py")), [])
        self.assertEqual(sorted(p.name for p in (root / "assets").iterdir() if p.suffix == ".py"), [])
        for name in ("zotero_helper.py", "reorganize_notes.py", "paper_daemon.py"):
            self.assertTrue((root / "scripts" / name).exists(), name)
        self.assertTrue((root / "assets" / "paper-note-template.md").exists())

    def test_daily_papers_layout(self):
        root = SKILLS / "daily-papers"
        self.assertEqual(sorted(root.glob("*.py")), [])
        for name in ("fetch_and_score.py", "enrich_papers.py", "parse_arxiv.py",
                     "extract_affiliations.py", "download_note_images.py"):
            self.assertTrue((root / "scripts" / name).exists(), name)

    def test_readme_and_architecture_state_directory_convention(self):
        for doc in (REPO_ROOT / "README.md", REPO_ROOT / "ARCHITECTURE.md"):
            text = doc.read_text(encoding="utf-8")
            for cell in ("`scripts/`", "`references/`", "`assets/`"):
                self.assertIn(cell, text, doc.name)

    def test_architecture_has_no_machine_specific_paths(self):
        text = (REPO_ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
        self.assertNotIn("/Users/bytedance", text)
        self.assertNotIn("/Users/beenli", text)


if __name__ == "__main__":
    unittest.main()
