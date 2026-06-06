"""Persistência do estado entre execuções efêmeras (GitHub Actions)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import requests

from config import MARKET_REFERENCE_SEED_BRL, STATE_VARIABLE_NAME


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_state() -> dict[str, Any]:
    return {
        "reference_price_brl": MARKET_REFERENCE_SEED_BRL,
        "target_price_brl": round(MARKET_REFERENCE_SEED_BRL * 0.65, 2),
        "last_notified_price_brl": None,
        "last_green_notified_price_brl": None,
        "last_yellow_notified_price_brl": None,
        "yellow_target_price_brl": None,
        "last_cheapest": None,
        "serpapi_date_cursor": 0,
        "reference_updated_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
    }


def load_state() -> dict[str, Any]:
    inline = os.getenv("FLIGHT_TRACKER_STATE")
    if inline:
        try:
            return {**default_state(), **json.loads(inline)}
        except json.JSONDecodeError:
            pass

    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_PAT")
    repo = os.getenv("GITHUB_REPOSITORY")
    if not token or not repo:
        return default_state()

    owner, name = repo.split("/", 1)
    url = f"https://api.github.com/repos/{owner}/{name}/actions/variables/{STATE_VARIABLE_NAME}"
    resp = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30,
    )
    if resp.status_code == 404:
        return default_state()
    resp.raise_for_status()
    value = resp.json().get("value", "")
    if not value:
        return default_state()
    try:
        return {**default_state(), **json.loads(value)}
    except json.JSONDecodeError:
        return default_state()


def save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = _utc_now_iso()
    payload = json.dumps(state, ensure_ascii=False)

    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_PAT")
    repo = os.getenv("GITHUB_REPOSITORY")
    if not token or not repo:
        os.environ["FLIGHT_TRACKER_STATE"] = payload
        return

    owner, name = repo.split("/", 1)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    base = f"https://api.github.com/repos/{owner}/{name}/actions/variables"
    var_url = f"{base}/{STATE_VARIABLE_NAME}"

    get_resp = requests.get(var_url, headers=headers, timeout=30)
    if get_resp.status_code == 404:
        create = requests.post(
            base,
            headers=headers,
            json={"name": STATE_VARIABLE_NAME, "value": payload},
            timeout=30,
        )
        create.raise_for_status()
        return

    patch = requests.patch(
        var_url,
        headers=headers,
        json={"name": STATE_VARIABLE_NAME, "value": payload},
        timeout=30,
    )
    patch.raise_for_status()
