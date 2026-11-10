from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import bkt, store
from app.problems import check_answer, generate_problem
from app.skills import (
    MASTERY_THRESHOLD,
    SKILLS,
    is_unlocked,
    missing_prereqs,
    select_difficulty,
    skill_order,
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Basis")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


# --------------------------------------------------------------------------- models

class SessionStartRequest(BaseModel):
    student_id: str
    skill_id: str


class SubmitRequest(BaseModel):
    problem_id: str
    answer: str


# --------------------------------------------------------------------------- helpers

def _mastery_map(student_id: str) -> dict[str, float]:
    return {sid: store.get_mastery(student_id, sid, SKILLS[sid].p_init) for sid in SKILLS}


def _topic_payload(student_id: str) -> list[dict]:
    mastery_map = _mastery_map(student_id)
    payload = []
    for skill_id in skill_order():
        skill = SKILLS[skill_id]
        mastery = mastery_map[skill_id]
        locked = not is_unlocked(skill_id, mastery_map)
        band = skill.group if not locked else f"locked - needs {', '.join(SKILLS[p].label for p in missing_prereqs(skill_id, mastery_map))}"
        payload.append({
            "key": skill_id,
            "label": skill.label,
            "band": band,
            "group": skill.group,
            "locked": locked,
            "mastery": round(mastery, 3),
            "mastered": mastery >= MASTERY_THRESHOLD,
        })
    return payload


# --------------------------------------------------------------------------- routes

@app.get("/api/topics")
def list_topics(student_id: str):
    return _topic_payload(student_id)


@app.post("/api/session/start")
def start_session(req: SessionStartRequest):
    if req.skill_id not in SKILLS:
        raise HTTPException(404, f"unknown skill '{req.skill_id}'")

    mastery_map = _mastery_map(req.student_id)
    if not is_unlocked(req.skill_id, mastery_map):
        missing = [SKILLS[p].label for p in missing_prereqs(req.skill_id, mastery_map)]
        raise HTTPException(403, f"'{SKILLS[req.skill_id].label}' is locked - build up {', '.join(missing)} first")

    session_id = store.create_session(req.student_id, req.skill_id)
    mastery = mastery_map[req.skill_id]
    return {
        "session_id": session_id,
        "skill_id": req.skill_id,
        "label": SKILLS[req.skill_id].label,
        "mastery": round(mastery, 3),
        "difficulty": select_difficulty(mastery),
    }


@app.get("/api/session/{session_id}/problem")
def get_problem(session_id: str):
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(404, "session not found")

    mastery = store.get_mastery(session["student_id"], session["skill_id"], SKILLS[session["skill_id"]].p_init)
    difficulty = select_difficulty(mastery)
    problem = generate_problem(session["skill_id"], difficulty)
    problem.problem_id = uuid4().hex
    store.set_pending_problem(session_id, problem)

    return {
        "problem_id": problem.problem_id,
        "question": problem.question,
        "difficulty": difficulty,
        "skill_id": session["skill_id"],
        "mastery": round(mastery, 3),
    }


@app.post("/api/session/{session_id}/submit")
def submit_answer(session_id: str, req: SubmitRequest):
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(404, "session not found")

    problem = store.pop_pending_problem(session_id, req.problem_id)
    if problem is None:
        raise HTTPException(400, "no matching pending problem - fetch a new one")

    student_id, skill_id = session["student_id"], session["skill_id"]
    skill = SKILLS[skill_id]

    mastery_before = store.get_mastery(student_id, skill_id, skill.p_init)
    correct = check_answer(problem.answer_kind, problem.correct_answer, req.answer)

    params = skill.bkt_params(problem.difficulty)
    _, mastery_after = bkt.update_mastery(mastery_before, correct, params)
    store.set_mastery(student_id, skill_id, mastery_after)

    mastery_map_before = _mastery_map(student_id)
    mastery_map_before[skill_id] = mastery_before
    mastery_map_after = _mastery_map(student_id)

    newly_unlocked = [
        SKILLS[sid].label for sid in SKILLS
        if is_unlocked(sid, mastery_map_after) and not is_unlocked(sid, mastery_map_before)
    ]

    return {
        "correct": correct,
        "correct_answer": problem.correct_answer,
        "mastery_before": round(mastery_before, 3),
        "mastery_after": round(mastery_after, 3),
        "difficulty": problem.difficulty,
        "next_difficulty": select_difficulty(mastery_after),
        "mastered": mastery_after >= MASTERY_THRESHOLD,
        "newly_unlocked": newly_unlocked,
    }
