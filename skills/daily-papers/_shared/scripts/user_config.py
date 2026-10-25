#!/usr/bin/env python3

import copy
import json
import os
from functools import lru_cache
from pathlib import Path


# 关键词、类别等推荐默认值只写在 ../user-config.json；这里只兜底结构和路径，避免两份默认值漂移。
DEFAULT_CONFIG = {
    "paths": {
        "obsidian_vault": "~/ObsidianVault",
        "paper_notes_folder": "PaperNotes",
        "daily_papers_folder": "DailyPapers",
        "concepts_folder": "_concepts",
        "zotero_db": "~/Zotero/zotero.sqlite",
        "zotero_storage": "~/Zotero/storage",
        "zotero_base_attachment_path": "",
    },
    "daily_papers": {
        "keywords": [],
        "negative_keywords": [],
        "domain_boost_keywords": [],
        "focus_phrases": [],
        "venue_rank_scores": {},
        "arxiv_categories": ["cs.AR", "cs.DC", "cs.NI", "cs.OS", "cs.PF", "cs.ET", "cs.LG"],
        "min_score": 3,
        "top_n": 20,
    },
    "automation": {
        "auto_refresh_indexes": True,
        "git_commit": False,
        "git_push": False,
    },
    "mocs": {
        "filename_prefix": "",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


# 个人配置放在 skill 目录之外，`npx skills update` / plugin 更新覆盖 skill 目录时不会丢。
CONFIG_ENV_VAR = "ARCH_READING_CONFIG"
USER_CONFIG_PATH = Path("~/.config/arch-reading-skills/user-config.json")
# 旧位置：skill 目录内、被 .gitignore 忽略的覆盖文件，只为兼容迁移前的安装。
LEGACY_LOCAL_FILENAME = "user-config.local.json"


def user_override_paths(shared_dir: Path) -> list[Path]:
    """返回要叠加在默认值之上的个人配置文件：三个来源互斥，只取一个。

    设置了 ARCH_READING_CONFIG 就只用它，文件不存在也不再往下找（测试靠这一点隔离本机配置）；
    否则用 ~/.config 下的文件；两者都没有时才兜底读旧的 skill 目录内 local 文件。
    """
    env_path = os.environ.get(CONFIG_ENV_VAR)
    if env_path:
        return [Path(env_path).expanduser()]
    user_path = USER_CONFIG_PATH.expanduser()
    if user_path.exists():
        return [user_path]
    return [shared_dir / LEGACY_LOCAL_FILENAME]


@lru_cache(maxsize=1)
def load_user_config() -> dict:
    config = copy.deepcopy(DEFAULT_CONFIG)
    shared_dir = Path(__file__).resolve().parent.parent

    for config_path in [shared_dir / "user-config.json", *user_override_paths(shared_dir)]:
        if not config_path.exists():
            continue
        with config_path.open("r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            _deep_merge(config, loaded)

    return config


def _expand(path_value: str) -> Path:
    return Path(path_value).expanduser()


def paths_config() -> dict:
    return load_user_config()["paths"]


def daily_papers_config() -> dict:
    return load_user_config()["daily_papers"]


def automation_config() -> dict:
    config = load_user_config()["automation"]
    if config.get("git_push") and not config.get("git_commit"):
        config = copy.deepcopy(config)
        config["git_push"] = False
    return config


def obsidian_vault_path() -> Path:
    return _expand(paths_config()["obsidian_vault"])


def paper_notes_dir() -> Path:
    return obsidian_vault_path() / paths_config()["paper_notes_folder"]


def daily_papers_dir() -> Path:
    return obsidian_vault_path() / paths_config()["daily_papers_folder"]


def concepts_dir() -> Path:
    return paper_notes_dir() / paths_config()["concepts_folder"]


def zotero_db_path() -> Path:
    return _expand(paths_config()["zotero_db"])


def zotero_storage_dir() -> Path:
    return _expand(paths_config()["zotero_storage"])


def zotero_base_attachment_dir() -> Path | None:
    """Base directory for linked files stored as `attachments:<relpath>` (ZotMoov etc.)."""
    value = paths_config().get("zotero_base_attachment_path") or ""
    return _expand(value) if value else None


def auto_refresh_indexes_enabled() -> bool:
    return bool(automation_config()["auto_refresh_indexes"])


def git_commit_enabled() -> bool:
    return bool(automation_config()["git_commit"])


def git_push_enabled() -> bool:
    return bool(automation_config()["git_push"])


def mocs_config() -> dict:
    return load_user_config().get("mocs", {})


def moc_filename_prefix() -> str:
    return str(mocs_config().get("filename_prefix", "") or "")
