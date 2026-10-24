import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "skills" / "repo-reader"
SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

README = """# demo

Some intro text.

```bash
python3 scripts/run.py --days 3
npm install
make build \\
  ARGS=1
pip install -r requirements.txt
$ echo skip
```

Trailing prose.
"""


@pytest.fixture
def fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "demo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "docs").mkdir()
    (repo / "node_modules" / "x").mkdir(parents=True)
    (repo / "__pycache__").mkdir()
    (repo / "README.md").write_text(README, encoding="utf-8")
    (repo / "scripts" / "run.py").write_text("print('hi')\n", encoding="utf-8")
    (repo / "package.json").write_text("{}\n", encoding="utf-8")
    (repo / "package-lock.json").write_text("{}\n", encoding="utf-8")
    (repo / "config.yaml").write_text("a: 1\n", encoding="utf-8")
    (repo / "docs" / "guide.md").write_text("# guide\n", encoding="utf-8")
    (repo / "node_modules" / "x" / "index.js").write_text("", encoding="utf-8")
    (repo / "__pycache__" / "a.pyc").write_bytes(b"")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init"],
        cwd=repo,
        check=True,
    )
    return repo
