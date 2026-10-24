#!/usr/bin/env python3

import copy
import json
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


@lru_cache(maxsize=1)
def load_user_config() -> dict:
    config = copy.deepcopy(DEFAULT_CONFIG)
    config_dir = Path(__file__).resolve().parent.parent

    for filename in ("user-config.json", "user-config.local.json"):
        config_path = config_dir / filename
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
