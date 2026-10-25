import importlib.util
import json
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
USER_CONFIG_PY = REPO_ROOT / "skills" / "_shared" / "scripts" / "user_config.py"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    """在临时目录搭一个 _shared，HOME 指向临时目录，返回 (加载函数, shared 目录, home)。"""
    shared = tmp_path / "skill" / "_shared"
    (shared / "scripts").mkdir(parents=True)
    shutil.copy(USER_CONFIG_PY, shared / "scripts" / "user_config.py")
    (shared / "user-config.json").write_text(json.dumps({"paths": {"obsidian_vault": "default"}}), encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("ARCH_READING_CONFIG", raising=False)

    def load():
        spec = importlib.util.spec_from_file_location("user_config_isolated", shared / "scripts" / "user_config.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.load_user_config()["paths"]["obsidian_vault"]

    return load, shared, home


def write_vault(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"paths": {"obsidian_vault": value}}), encoding="utf-8")


def test_defaults_only(setup):
    load, _, _ = setup
    assert load() == "default"


def test_xdg_config_overrides_defaults(setup):
    load, _, home = setup
    write_vault(home / ".config" / "arch-reading-skills" / "user-config.json", "xdg")
    assert load() == "xdg"


def test_env_var_wins_over_xdg(setup, monkeypatch, tmp_path):
    load, _, home = setup
    write_vault(home / ".config" / "arch-reading-skills" / "user-config.json", "xdg")
    write_vault(tmp_path / "custom.json", "env")
    monkeypatch.setenv("ARCH_READING_CONFIG", str(tmp_path / "custom.json"))
    assert load() == "env"


def test_env_var_pointing_to_missing_file_blocks_fallbacks(setup, monkeypatch, tmp_path):
    load, shared, home = setup
    write_vault(home / ".config" / "arch-reading-skills" / "user-config.json", "xdg")
    write_vault(shared / "user-config.local.json", "legacy")
    monkeypatch.setenv("ARCH_READING_CONFIG", str(tmp_path / "absent.json"))
    assert load() == "default"


def test_legacy_local_file_only_when_xdg_missing(setup):
    load, shared, home = setup
    write_vault(shared / "user-config.local.json", "legacy")
    assert load() == "legacy"
    write_vault(home / ".config" / "arch-reading-skills" / "user-config.json", "xdg")
    assert load() == "xdg"
