#!/usr/bin/env python3
"""Minimal client for writing to Zotero 10's local API (http://localhost:23119/api).

Writes go through the running Zotero app instead of editing zotero.sqlite, so
they show up in the UI at once, sync like any local edit, and cannot be
overwritten by an open Zotero. Each write needs a key that Zotero hands out
only after the user clicks Allow in a dialog; unless they choose "Always
Allow", the key works for a single write. Item versions guard against
overwriting a change made in the meantime.

See https://www.zotero.org/support/dev/web_api/v3/local_api
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "http://localhost:23119/api"
LIBRARY = "users/0"


class LocalApiError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class VersionConflict(LocalApiError):
    """The item changed after it was read; nothing was written."""


class ZoteroLocalApi:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, app_name: str = "dailypaper-skills", timeout: float = 30):
        self.base_url = base_url.rstrip("/")
        self.app_name = app_name
        self.timeout = timeout
        self._server_id: str | None = None
        self._key: str | None = None
        self._remember = False

    def _request(self, method: str, path: str, body=None, headers=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(f"{self.base_url}/{path.lstrip('/')}", data=data, method=method)
        request.add_header("Zotero-API-Version", "3")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        for name, value in (headers or {}).items():
            request.add_header(name, value)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status, response_headers, raw = response.status, response.headers, response.read()
        except urllib.error.HTTPError as error:
            status, response_headers, raw = error.code, error.headers, error.read()
        except (urllib.error.URLError, OSError) as error:
            raise LocalApiError(
                f"无法连接 Zotero 本地 API（{self.base_url}）：请确认 Zotero 10 已打开，"
                f"并在 设置 → 高级 里启用了本地 API（{error}）"
            ) from error
        # The API root answers in plain text; only JSON responses carry a payload.
        is_json = "json" in ((response_headers.get("Content-Type") if response_headers else "") or "")
        payload = json.loads(raw) if raw and is_json else None
        return status, response_headers, payload

    def server_id(self) -> str:
        if self._server_id is None:
            status, headers, _ = self._request("GET", "/")
            server_id = headers.get("Zotero-Server-ID") if headers else None
            if status != 200 or not server_id:
                raise LocalApiError(f"本地 API 没有返回 Zotero-Server-ID（HTTP {status}），写入需要 Zotero 10 及以上", status)
            self._server_id = server_id
        return self._server_id

    def get_item(self, key: str) -> dict:
        status, _, payload = self._request("GET", f"{LIBRARY}/items/{key}")
        if status != 200:
            raise LocalApiError(f"读取条目 {key} 失败（HTTP {status}）", status)
        return payload

    def authorize(self) -> None:
        status, headers, payload = self._request(
            "POST", "local/authorize", {"appName": self.app_name}, {"Zotero-Server-ID": self.server_id()}
        )
        if status == 403:
            raise LocalApiError("Zotero 里拒绝了这次写入授权，没有做任何修改", status)
        if status == 429:
            raise LocalApiError(f"授权请求太频繁，请 {headers.get('Retry-After', '60')} 秒后再试", status)
        if status != 200 or not payload or "key" not in payload:
            raise LocalApiError(f"写入授权失败（HTTP {status}）", status)
        self._key = payload["key"]
        self._remember = bool(payload.get("remember"))

    def update_item(self, key: str, changes: dict, version: int | None = None) -> None:
        """PATCH ``changes`` into item ``key``; raises VersionConflict if it changed since ``version``."""
        if version is None:
            version = self.get_item(key)["version"]
        for attempt in range(2):
            if self._key is None:
                self.authorize()
            status, _, _ = self._request(
                "PATCH",
                f"{LIBRARY}/items/{key}",
                changes,
                {
                    "Zotero-Server-ID": self.server_id(),
                    "Zotero-API-Key": self._key,
                    "If-Unmodified-Since-Version": str(version),
                },
            )
            if status == 401 and attempt == 0:
                self._key = None  # expired or already used: ask once more
                continue
            break
        if status == 204:
            if not self._remember:
                self._key = None  # single-use key was consumed by this write
            return
        if status == 412:
            raise VersionConflict(f"条目 {key} 在读取之后被改过，没有写入；请重新读取后再试", status)
        raise LocalApiError(f"修改条目 {key} 失败（HTTP {status}）", status)
