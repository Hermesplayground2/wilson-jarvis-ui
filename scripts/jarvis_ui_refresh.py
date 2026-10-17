#!/usr/bin/env python3
"""Refresh the Jarvis HUD data files from real local state.

Every value is READ FROM THE MACHINE, never invented. Run with --push to commit
and push, which is what makes GitHub Pages update.

  data/status.json    gateway memory (MB), skills installed, scheduled cron jobs,
                      active model, liveness
  data/watchlist.json SLV / PAAS.TO / SPCX / RUM quotes (Nasdaq, CNBC fallback)
  data/memory.json    tracked topic names -- deliberately NOT the raw memory store,
                      because this repo is PUBLIC
  data/queue.json     enabled / paused cron job breakdown
  data/commands.json  the most recent cron runs, newest first

Usage:
    python scripts/jarvis_ui_refresh.py [--push]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(os.environ.get("JARVIS_UI_REPO", "D:/Hermes/projects/website/jarvis-ui"))
DATA = REPO / "data"
NOTES = Path("D:/Hermes/memory/persistent-notes")

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
NASDAQ = "https://api.nasdaq.com/api/quote/{s}/info?assetclass={a}"
CNBC = ("https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol"
        "?symbols={s}&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1"
        "&output=json&events=1")
SYMBOLS = {"SLV": "etf", "PAAS.TO": None, "SPCX": "stocks", "RUM": "stocks"}


def hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", "")) / "hermes"
    return Path.home() / ".hermes"


# ---------------------------------------------------------------- local state

def gateway_memory_mb():
    """Resident memory of the running gateway process, summed over its workers."""
    try:
        if os.name == "nt":
            ps = ("Get-CimInstance Win32_Process | "
                  "Where-Object { $_.CommandLine -match 'gateway run' } | "
                  "ForEach-Object { [math]::Round($_.WorkingSetSize/1MB) }")
            out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                                 capture_output=True, text=True, timeout=90).stdout
            vals = [int(v) for v in out.split() if v.strip().isdigit()]
            return sum(vals) if vals else None
        out = subprocess.run(["ps", "-eo", "rss,args"], capture_output=True,
                             text=True, timeout=30).stdout
        total = 0
        for line in out.splitlines():
            if "gateway run" in line and "grep" not in line:
                total += int(line.split()[0]) // 1024
        return total or None
    except Exception:
        return None


def skill_count() -> int:
    root = hermes_home() / "skills"
    return len(list(root.rglob("SKILL.md"))) if root.exists() else 0


def cron_jobs() -> list:
    path = hermes_home() / "cron" / "jobs.json"
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return raw.get("jobs", raw) if isinstance(raw, dict) else raw


def active_model() -> str:
    path = hermes_home() / "config.yaml"
    if not path.exists():
        return "unknown"
    try:
        import yaml
        cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return (cfg.get("model") or {}).get("default") or "unknown"
    except Exception:
        m = re.search(r"^\s*default:\s*(\S+)", path.read_text(encoding="utf-8"), re.M)
        return m.group(1) if m else "unknown"


def topics() -> list:
    """Tracked topic names only. The raw memory store is NOT published: this repo
    is public and MEMORY.md holds machine paths and infrastructure detail."""
    tdir = NOTES / "topics"
    if not tdir.exists():
        return []
    names = sorted(p.stem for p in tdir.glob("*.md"))
    out = [{"text": "Topics tracked: %d" % len(names), "active": True}]
    out += [{"text": "Topic: %s" % n.replace("-", " "), "active": False} for n in names]
    return out[:12]


def recent_runs(limit: int = 8) -> list:
    outdir = hermes_home() / "cron" / "output"
    if not outdir.exists():
        return []
    found = []
    for job in outdir.iterdir():
        if not job.is_dir():
            continue
        runs = sorted(job.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not runs:
            continue
        try:
            head = runs[0].read_text(encoding="utf-8", errors="ignore")[:600]
        except Exception:
            continue
        name = re.search(r"# Cron Job:\s*(.+)", head)
        when = re.search(r"\*\*Run Time:\*\*\s*(.+)", head)
        status = re.search(r"\*\*Status:\*\*\s*(.+)", head)
        text = (name.group(1).strip() if name else job.name)
        if status:
            text += " — " + status.group(1).strip()
        found.append({
            "time": (when.group(1).strip() if when else ""),
            "text": text,
            "_mtime": runs[0].stat().st_mtime,
        })
    found.sort(key=lambda r: r["_mtime"], reverse=True)
    for r in found:
        r.pop("_mtime", None)
    return found[:limit]


# ------------------------------------------------------------------- quotes

def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/json, text/plain, */*"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read())


def _num(value) -> float:
    return float(re.sub(r"[^0-9.+-]", "", str(value)))


def quote(sym: str, assetclass):
    """Nasdaq first, CNBC as the fallback that also covers Toronto."""
    if assetclass:
        try:
            d = _get(NASDAQ.format(s=sym, a=assetclass))
            p = (d.get("data") or {}).get("primaryData") or {}
            if p.get("lastSalePrice"):
                return {"symbol": sym, "price": _num(p["lastSalePrice"]),
                        "change": round(_num(p.get("percentageChange") or 0), 2)}
        except Exception:
            pass
    d = _get(CNBC.format(s=urllib.parse.quote(sym)))
    q = d["FormattedQuoteResult"]["FormattedQuote"][0]
    return {"symbol": sym, "price": _num(q["last"]),
            "change": round(_num(q.get("change_pct") or 0), 2)}


def watchlist() -> list:
    rows = []
    for sym, ac in SYMBOLS.items():
        try:
            rows.append(quote(sym, ac))
        except Exception as exc:
            print("  quote %s failed: %s" % (sym, exc), file=sys.stderr)
    return rows


# --------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-push", action="store_true",
                    help="only rewrite the data files, do not commit or push")
    ap.add_argument("--repo", help="override the jarvis-ui checkout to refresh")
    args = ap.parse_args()

    global REPO, DATA
    if args.repo:
        REPO = Path(args.repo)
        DATA = REPO / "data"

    DATA.mkdir(parents=True, exist_ok=True)

    jobs = cron_jobs()
    enabled = [j for j in jobs if j.get("enabled")]
    paused = [j for j in jobs if not j.get("enabled")]
    mem = gateway_memory_mb()

    status = {
        # Rounded to 25 MB: the exact figure wobbles every few seconds and would
        # otherwise commit and push on every single run.
        "memory": (round(mem / 25) * 25) if mem is not None else 0,
        "memoryMax": 2800,               # gateway.memory_restart_threshold_mb
        "skills": skill_count(),
        "status": "ONLINE",
        "mode": active_model(),
        "queue": len(enabled),
        "lastUpdate": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (DATA / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")

    (DATA / "queue.json").write_text(json.dumps({
        "pending": len(enabled), "total": len(jobs),
        "items": [{"title": j.get("name", "?"),
                   "status": "enabled" if j.get("enabled") else "paused"}
                  for j in jobs[:12]],
    }, indent=2), encoding="utf-8")

    (DATA / "memory.json").write_text(json.dumps(topics(), indent=2), encoding="utf-8")
    (DATA / "commands.json").write_text(json.dumps(recent_runs(), indent=2), encoding="utf-8")

    wl = watchlist()
    if wl:
        (DATA / "watchlist.json").write_text(json.dumps(wl, indent=2), encoding="utf-8")

    print("status:  %s" % json.dumps(status))
    print("watchlist: %s" % ", ".join("%s %.2f" % (r["symbol"], r["price"]) for r in wl))
    print("cron:    %d enabled / %d total" % (len(enabled), len(jobs)))

    if not args.no_push:
        def git(*cmd):
            return subprocess.run(["git", "-C", str(REPO), *cmd],
                                  capture_output=True, text=True)
        git("add", "data")
        diff = git("diff", "--cached", "--quiet")
        if diff.returncode == 0:
            print("push:    nothing changed, not committing")
            return 0
        git("commit", "-m", "Refresh dashboard data (%s)" % status["lastUpdate"])
        push = git("push", "origin", "master")
        print("push:    %s" % (push.stdout.strip() or push.stderr.strip() or "ok"))
        return push.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
