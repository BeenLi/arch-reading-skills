import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_vendored_shared_copies_match_source():
    """skills/<name>/_shared 是 skills/_shared 的生成副本；改了源却没重新生成时这里会失败。"""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "sync_shared.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
