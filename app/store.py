"""Persistence.

Per-student mastery estimates are small and simple enough to not need a
real database for this project: they're kept in memory and mirrored to a
JSON file so progress survives a server restart. Sessions (which problem
is currently pending for which student/skill) are transient and live in
memory only.
"""

import json
import threading
import uuid
from pathlib import Path
from typing import Optional

from app.problems import GeneratedProblem

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "students.json"

_lock = threading.Lock()


def _load() -> dict:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _save() -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(_students, indent=2))


_students: dict[str, dict[str, float]] = _load()
_sessions: dict[str, dict] = {}


def get_mastery(student_id: str, skill_id: str, default: float) -> float:
    return _students.get(student_id, {}).get(skill_id, default)


def get_all_mastery(student_id: str) -> dict[str, float]:
    return dict(_students.get(student_id, {}))


def set_mastery(student_id: str, skill_id: str, value: float) -> None:
    with _lock:
        _students.setdefault(student_id, {})[skill_id] = value
        _save()


def create_session(student_id: str, skill_id: str) -> str:
    session_id = uuid.uuid4().hex
    _sessions[session_id] = {"student_id": student_id, "skill_id": skill_id, "pending": None}
    return session_id


def get_session(session_id: str) -> Optional[dict]:
    return _sessions.get(session_id)


def set_pending_problem(session_id: str, problem: GeneratedProblem) -> None:
    _sessions[session_id]["pending"] = problem


def pop_pending_problem(session_id: str, problem_id: str) -> Optional[GeneratedProblem]:
    session = _sessions.get(session_id)
    if not session or session["pending"] is None:
        return None
    if session["pending"].problem_id != problem_id:
        return None
    problem = session["pending"]
    session["pending"] = None
    return problem
