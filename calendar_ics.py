import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


def _unfold_ics_lines(text: str) -> List[str]:
    lines = text.splitlines()
    out: List[str] = []
    for line in lines:
        if not line:
            continue
        if line.startswith((" ", "\t")) and out:
            out[-1] = out[-1] + line[1:]
        else:
            out.append(line)
    return out


def _parse_dt(value: str, tzid: Optional[str]) -> Optional[datetime]:
    value = value.strip()
    if not value:
        return None
    # All-day: YYYYMMDD
    if re.fullmatch(r"\d{8}", value):
        dt = datetime.strptime(value, "%Y%m%d").replace(tzinfo=timezone.utc)
        return dt
    # Date-time: YYYYMMDDTHHMMSSZ or without seconds.
    zulu = value.endswith("Z")
    raw = value[:-1] if zulu else value
    fmt = "%Y%m%dT%H%M%S" if len(raw) == 15 else "%Y%m%dT%H%M"
    try:
        dt = datetime.strptime(raw, fmt)
    except Exception:
        return None
    if zulu:
        return dt.replace(tzinfo=timezone.utc)
    if tzid and ZoneInfo:
        try:
            return dt.replace(tzinfo=ZoneInfo(tzid))
        except Exception:
            pass
    # Floating time: treat as local/unknown; keep naive but assume UTC for matching.
    return dt.replace(tzinfo=timezone.utc)


def _parse_params(key_with_params: str) -> Tuple[str, Dict[str, str]]:
    # Example: DTSTART;TZID=Europe/Berlin;VALUE=DATE-TIME
    parts = key_with_params.split(";")
    key = parts[0].upper()
    params: Dict[str, str] = {}
    for p in parts[1:]:
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        params[k.upper()] = v
    return key, params


def parse_ics(text: str) -> List[Dict[str, Any]]:
    lines = _unfold_ics_lines(text)
    events: List[Dict[str, Any]] = []
    cur: Dict[str, Any] = {}
    in_event = False

    for line in lines:
        if line == "BEGIN:VEVENT":
            cur = {"attendees": []}
            in_event = True
            continue
        if line == "END:VEVENT":
            if in_event and cur.get("uid") and cur.get("start") and cur.get("end"):
                events.append(cur)
            cur = {}
            in_event = False
            continue
        if not in_event:
            continue
        if ":" not in line:
            continue
        left, value = line.split(":", 1)
        key, params = _parse_params(left)
        if key == "UID":
            cur["uid"] = value.strip()
        elif key == "SUMMARY":
            cur["summary"] = value.strip()
        elif key == "LOCATION":
            cur["location"] = value.strip()
        elif key == "DESCRIPTION":
            cur["description"] = value.strip()
        elif key in ("DTSTART", "DTEND"):
            tzid = params.get("TZID")
            dt = _parse_dt(value, tzid)
            if dt:
                cur["start" if key == "DTSTART" else "end"] = dt
        elif key == "ATTENDEE":
            attendee = {"name": params.get("CN") or None, "value": value.strip()}
            # Normalize mailto:
            if attendee["value"].lower().startswith("mailto:"):
                attendee["email"] = attendee["value"][7:]
            cur.setdefault("attendees", []).append(attendee)

    # Normalize to JSON-safe output.
    out: List[Dict[str, Any]] = []
    for ev in events:
        out.append(
            {
                "uid": ev.get("uid"),
                "summary": ev.get("summary") or "(no title)",
                "start": ev["start"].astimezone(timezone.utc).isoformat(),
                "end": ev["end"].astimezone(timezone.utc).isoformat(),
                "location": ev.get("location"),
                "description": ev.get("description"),
                "attendees": [
                    {"name": a.get("name"), "email": a.get("email")}
                    for a in (ev.get("attendees") or [])
                ],
            }
        )
    return out


def _score_event(session_time: datetime, start: datetime, end: datetime) -> float:
    if end <= start:
        return 0.0
    if start <= session_time <= end:
        # In-event: higher if closer to midpoint.
        mid = start + (end - start) / 2
        dist = abs((session_time - mid).total_seconds())
        return 1.0 / (1.0 + dist / 60.0)
    # Outside: penalize by minutes to boundary.
    boundary = start if session_time < start else end
    dist = abs((session_time - boundary).total_seconds())
    return 1.0 / (1.0 + dist / 60.0)


def fetch_ics_events(url: str, cache_path: Path, max_age_seconds: int = 600) -> List[Dict[str, Any]]:
    if not url:
        return []
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("url") == url and cached.get("fetched_at"):
                fetched_at = datetime.fromisoformat(cached["fetched_at"])
                age = (now - fetched_at).total_seconds()
                if age <= max_age_seconds:
                    return cached.get("events") or []
        except Exception:
            pass

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    events = parse_ics(resp.text)
    cache_path.write_text(
        json.dumps({"url": url, "fetched_at": now.isoformat(), "events": events}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return events


def suggest_events(
    *,
    events: List[Dict[str, Any]],
    session_time_iso: str,
    window_minutes: int = 45,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    try:
        session_time = datetime.fromisoformat(session_time_iso)
    except Exception:
        return []
    if session_time.tzinfo is None:
        session_time = session_time.replace(tzinfo=timezone.utc)
    session_time = session_time.astimezone(timezone.utc)

    window_sec = max(1, int(window_minutes) * 60)
    candidates: List[Tuple[float, Dict[str, Any]]] = []
    for ev in events:
        try:
            start = datetime.fromisoformat(ev["start"]).astimezone(timezone.utc)
            end = datetime.fromisoformat(ev["end"]).astimezone(timezone.utc)
        except Exception:
            continue
        # Filter by window to keep suggestions relevant.
        near = False
        if start <= session_time <= end:
            near = True
        else:
            dist = min(abs((session_time - start).total_seconds()), abs((session_time - end).total_seconds()))
            near = dist <= window_sec
        if not near:
            continue
        score = _score_event(session_time, start, end)
        candidates.append((score, ev))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [{"score": s, **ev} for s, ev in candidates[:limit]]

