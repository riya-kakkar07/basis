"""The skill prerequisite graph for algebra fundamentals.

This is a DAG: each node is a skill, edges point from a skill to the
skills that depend on it. A skill is "unlocked" for a student once all of
its prerequisites are at or above UNLOCK_THRESHOLD mastery.

Each skill also carries its own BKT parameters. p_init/p_transit describe
the skill itself (how likely a brand-new student already knows it, and how
fast practice teaches it); guess/slip are given per difficulty tier since
easier items are more guessable and harder items are more slip-prone for a
student who genuinely knows the material (KT-IDEM style).
"""

from dataclasses import dataclass, field

from app.bkt import BKTParams

DIFFICULTIES = ("easy", "medium", "hard")

UNLOCK_THRESHOLD = 0.60   # prereq mastery needed to unlock a dependent skill
MASTERY_THRESHOLD = 0.95  # mastery considered "learned"


@dataclass(frozen=True)
class Skill:
    id: str
    label: str
    group: str
    prereqs: tuple[str, ...]
    p_init: float
    p_transit: float
    # guess/slip per difficulty tier
    guess_slip: dict = field(default_factory=dict)

    def bkt_params(self, difficulty: str) -> BKTParams:
        guess, slip = self.guess_slip[difficulty]
        return BKTParams(p_init=self.p_init, p_transit=self.p_transit, p_guess=guess, p_slip=slip)


def _gs(easy, medium, hard):
    return {"easy": easy, "medium": medium, "hard": hard}


SKILLS: dict[str, Skill] = {}


def _add(id, label, group, prereqs, p_init, p_transit, guess_slip):
    SKILLS[id] = Skill(
        id=id, label=label, group=group, prereqs=tuple(prereqs),
        p_init=p_init, p_transit=p_transit, guess_slip=guess_slip,
    )


_add(
    "integer_arithmetic", "Integer Arithmetic", "Foundations", [],
    p_init=0.35, p_transit=0.20,
    guess_slip=_gs(easy=(0.30, 0.06), medium=(0.18, 0.10), hard=(0.08, 0.16)),
)
_add(
    "order_of_operations", "Order of Operations", "Foundations", ["integer_arithmetic"],
    p_init=0.25, p_transit=0.17,
    guess_slip=_gs(easy=(0.28, 0.08), medium=(0.16, 0.12), hard=(0.07, 0.18)),
)
_add(
    "fractions", "Fractions", "Foundations", ["integer_arithmetic"],
    p_init=0.25, p_transit=0.15,
    guess_slip=_gs(easy=(0.25, 0.08), medium=(0.14, 0.13), hard=(0.06, 0.20)),
)
_add(
    "combining_like_terms", "Combining Like Terms", "Expressions", ["order_of_operations"],
    p_init=0.20, p_transit=0.17,
    guess_slip=_gs(easy=(0.22, 0.08), medium=(0.12, 0.13), hard=(0.05, 0.19)),
)
_add(
    "distributive_property", "The Distributive Property", "Expressions", ["order_of_operations"],
    p_init=0.20, p_transit=0.17,
    guess_slip=_gs(easy=(0.22, 0.08), medium=(0.12, 0.13), hard=(0.05, 0.19)),
)
_add(
    "exponents", "Exponents", "Expressions", ["integer_arithmetic"],
    p_init=0.25, p_transit=0.18,
    guess_slip=_gs(easy=(0.25, 0.07), medium=(0.13, 0.12), hard=(0.05, 0.18)),
)
_add(
    "one_step_equations", "One-Step Equations", "Equations", ["integer_arithmetic"],
    p_init=0.25, p_transit=0.20,
    guess_slip=_gs(easy=(0.25, 0.07), medium=(0.14, 0.11), hard=(0.06, 0.17)),
)
_add(
    "two_step_equations", "Two-Step Equations", "Equations",
    ["one_step_equations", "combining_like_terms"],
    p_init=0.15, p_transit=0.16,
    guess_slip=_gs(easy=(0.18, 0.09), medium=(0.10, 0.14), hard=(0.04, 0.20)),
)
_add(
    "multi_step_equations", "Multi-Step Equations", "Equations",
    ["two_step_equations", "distributive_property"],
    p_init=0.10, p_transit=0.14,
    guess_slip=_gs(easy=(0.15, 0.10), medium=(0.08, 0.15), hard=(0.03, 0.22)),
)
_add(
    "slope", "Slope of a Line", "Graphing & Systems", ["fractions", "integer_arithmetic"],
    p_init=0.15, p_transit=0.16,
    guess_slip=_gs(easy=(0.18, 0.08), medium=(0.10, 0.13), hard=(0.04, 0.19)),
)
_add(
    "slope_intercept_form", "Slope-Intercept Form", "Graphing & Systems",
    ["slope", "two_step_equations"],
    p_init=0.10, p_transit=0.15,
    guess_slip=_gs(easy=(0.15, 0.09), medium=(0.08, 0.14), hard=(0.03, 0.20)),
)
_add(
    "systems_of_equations", "Systems of Equations", "Graphing & Systems",
    ["multi_step_equations", "slope_intercept_form"],
    p_init=0.08, p_transit=0.13,
    guess_slip=_gs(easy=(0.12, 0.10), medium=(0.06, 0.16), hard=(0.02, 0.24)),
)
_add(
    "factoring_quadratics", "Factoring Quadratics", "Quadratics",
    ["distributive_property", "exponents"],
    p_init=0.08, p_transit=0.13,
    guess_slip=_gs(easy=(0.12, 0.10), medium=(0.06, 0.16), hard=(0.02, 0.24)),
)
_add(
    "percentages", "Percentages", "Foundations", ["fractions"],
    p_init=0.20, p_transit=0.16,
    guess_slip=_gs(easy=(0.22, 0.08), medium=(0.12, 0.13), hard=(0.05, 0.19)),
)
_add(
    "ratios_proportions", "Ratios & Proportions", "Foundations", ["fractions"],
    p_init=0.18, p_transit=0.16,
    guess_slip=_gs(easy=(0.20, 0.08), medium=(0.11, 0.13), hard=(0.05, 0.19)),
)
_add(
    "absolute_value_equations", "Absolute Value Equations", "Equations", ["one_step_equations"],
    p_init=0.15, p_transit=0.15,
    guess_slip=_gs(easy=(0.16, 0.09), medium=(0.09, 0.14), hard=(0.04, 0.20)),
)
_add(
    "inequalities", "Inequalities", "Equations", ["two_step_equations"],
    p_init=0.12, p_transit=0.15,
    guess_slip=_gs(easy=(0.15, 0.09), medium=(0.08, 0.14), hard=(0.03, 0.21)),
)
_add(
    "polynomial_add_sub", "Adding & Subtracting Polynomials", "Expressions",
    ["combining_like_terms", "exponents"],
    p_init=0.15, p_transit=0.15,
    guess_slip=_gs(easy=(0.17, 0.09), medium=(0.09, 0.14), hard=(0.04, 0.20)),
)


def skill_order() -> list[str]:
    """Topological order, so prerequisites always appear before dependents."""
    order: list[str] = []
    visited: set[str] = set()

    def visit(skill_id: str) -> None:
        if skill_id in visited:
            return
        visited.add(skill_id)
        for prereq in SKILLS[skill_id].prereqs:
            visit(prereq)
        order.append(skill_id)

    for skill_id in SKILLS:
        visit(skill_id)
    return order


def select_difficulty(mastery: float) -> str:
    if mastery < 0.40:
        return "easy"
    if mastery < 0.75:
        return "medium"
    return "hard"


def is_unlocked(skill_id: str, mastery_by_skill: dict[str, float]) -> bool:
    skill = SKILLS[skill_id]
    if not skill.prereqs:
        return True
    return all(mastery_by_skill.get(p, SKILLS[p].p_init) >= UNLOCK_THRESHOLD for p in skill.prereqs)


def missing_prereqs(skill_id: str, mastery_by_skill: dict[str, float]) -> list[str]:
    skill = SKILLS[skill_id]
    return [
        p for p in skill.prereqs
        if mastery_by_skill.get(p, SKILLS[p].p_init) < UNLOCK_THRESHOLD
    ]
