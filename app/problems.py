"""Procedural problem generation and answer checking.

Every problem is generated fresh (random values, chosen server-side) rather
than pulled from a fixed bank, so practice never runs out. `eval()` only
ever runs on numeric expressions this module built itself out of its own
random integers - never on anything a client sent.

Student-submitted answers, by contrast, are untrusted text. They're
checked with sympy so equivalent forms (e.g. "4/8" vs "1/2", "2x+7" vs
"7+2x") are accepted, but the raw string is restricted to a tight
whitelist of math characters before it ever reaches sympy's parser.
"""

import random
import re
from dataclasses import dataclass
from fractions import Fraction

from sympy import Eq, expand, simplify
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    standard_transformations,
    parse_expr,
)

_TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application, convert_xor)
_SAFE_PATTERN = re.compile(r"^[0-9xyXY\.\+\-\*/\^\(\)\,\s]{1,60}$")
_INEQUALITY_PATTERN = re.compile(r"^\s*x\s*(<=|>=|<|>)\s*([0-9\.\+\-\*/\^\(\)\s]{1,30})\s*$", re.IGNORECASE)


class InvalidAnswer(Exception):
    pass


def _safe_parse(text: str):
    if not text or not _SAFE_PATTERN.match(text):
        raise InvalidAnswer(f"unexpected characters in answer: {text!r}")
    return parse_expr(text.replace("^", "**"), transformations=_TRANSFORMATIONS, evaluate=True)


@dataclass
class GeneratedProblem:
    skill_id: str
    difficulty: str
    question: str
    answer_kind: str  # "number" | "linear_expr" | "xy_pair" | "root_pair" | "inequality"
    correct_answer: str
    problem_id: str = ""


def _fmt_term(coef: int, var: str, is_first: bool) -> str:
    if coef == 0:
        return ""
    sign = "-" if coef < 0 else ("" if is_first else "+")
    magnitude = abs(coef)
    body = f"{magnitude}{var}" if (magnitude != 1 or not var) else var
    if is_first:
        return f"{sign}{body}"
    return f" {sign} {body}"


def _format_linear(x_coef: int, const: int) -> str:
    parts = []
    if x_coef != 0:
        parts.append(_fmt_term(x_coef, "x", is_first=True))
    if const != 0 or not parts:
        parts.append(_fmt_term(const, "", is_first=not parts))
    text = "".join(parts).strip()
    return text if text else "0"


def _nonzero(lo: int, hi: int) -> int:
    val = 0
    while val == 0:
        val = random.randint(lo, hi)
    return val


def _new(skill_id: str, difficulty: str, question: str, answer_kind: str, correct_answer: str) -> GeneratedProblem:
    return GeneratedProblem(
        skill_id=skill_id, difficulty=difficulty, question=question,
        answer_kind=answer_kind, correct_answer=correct_answer,
    )


# ---------------------------------------------------------------- Foundations

def gen_integer_arithmetic(difficulty: str) -> GeneratedProblem:
    if difficulty == "easy":
        a, b = random.randint(1, 12), random.randint(1, 12)
        op = random.choice(["+", "-"])
    elif difficulty == "medium":
        a, b = random.randint(-15, 20), random.randint(-15, 20)
        op = random.choice(["+", "-", "*"])
    else:
        op = random.choice(["+", "-", "*", "/"])
        if op == "/":
            b = random.choice(range(2, 13))
            a = b * random.randint(-9, 9)
        else:
            a, b = random.randint(-25, 25), random.randint(-20, 20)
    expr = f"({a}) {op} ({b})"
    answer = eval(expr)  # nosec: a, op, b are all server-generated above
    return _new("integer_arithmetic", difficulty, f"{a} {op} {b} = ?", "number", str(answer))


def gen_order_of_operations(difficulty: str) -> GeneratedProblem:
    if difficulty == "easy":
        a, b, c = (random.randint(1, 10) for _ in range(3))
        expr = f"{a} + {b} * {c}"
    elif difficulty == "medium":
        a, b, c, d = (random.randint(1, 10) for _ in range(4))
        expr = f"({a} + {b}) * {c} - {d}"
    else:
        a, b, c, d, e = (random.randint(1, 10) for _ in range(5))
        expr = f"{a} * ({b} - {c}) + {d} * {e}"
    answer = eval(expr)  # nosec: expr built only from our own randint() calls
    return _new("order_of_operations", difficulty, f"{expr} = ?", "number", str(answer))


def gen_fractions(difficulty: str) -> GeneratedProblem:
    max_den = {"easy": 6, "medium": 10, "hard": 12}[difficulty]
    ops = ["+", "-"] if difficulty == "easy" else ["+", "-", "*"]

    def rand_frac() -> Fraction:
        d = random.randint(2, max_den)
        n = random.randint(1, d - 1)
        if random.random() < 0.3:
            n += d  # occasionally go over 1
        return Fraction(n, d)

    f1, f2 = rand_frac(), rand_frac()
    op = random.choice(ops)
    result = {"+": f1 + f2, "-": f1 - f2, "*": f1 * f2}[op]
    question = f"{f1.numerator}/{f1.denominator} {op} {f2.numerator}/{f2.denominator} = ?"
    answer = str(result.numerator) if result.denominator == 1 else f"{result.numerator}/{result.denominator}"
    return _new("fractions", difficulty, question, "number", answer)


# ---------------------------------------------------------------- Expressions

def gen_combining_like_terms(difficulty: str) -> GeneratedProblem:
    n_terms, coef_range = {
        "easy": (2, (1, 9)),
        "medium": (3, (-9, 9)),
        "hard": (4, (-15, 15)),
    }[difficulty]

    x_coefs, pieces = [], []
    for _ in range(n_terms):
        is_x = random.random() < 0.6 or not x_coefs
        coef = _nonzero(*coef_range)
        if is_x:
            x_coefs.append(coef)
            pieces.append(("x", coef))
        else:
            pieces.append(("", coef))
    random.shuffle(pieces)

    display = "".join(_fmt_term(coef, var, is_first=(i == 0)) for i, (var, coef) in enumerate(pieces))
    total_x = sum(c for v, c in pieces if v == "x")
    total_c = sum(c for v, c in pieces if v == "")
    answer = _format_linear(total_x, total_c)
    return _new("combining_like_terms", difficulty, f"Simplify: {display}", "linear_expr", answer)


def gen_distributive_property(difficulty: str) -> GeneratedProblem:
    rng = {"easy": (2, 9), "medium": (-9, 9), "hard": (-12, 12)}[difficulty]
    a = _nonzero(*rng)
    b = _nonzero(*rng)
    c = random.randint(rng[0], rng[1])
    inner = _format_linear(b, c)
    question = f"Expand: {a}({inner})"
    answer = _format_linear(a * b, a * c)
    return _new("distributive_property", difficulty, question, "linear_expr", answer)


def gen_exponents(difficulty: str) -> GeneratedProblem:
    if difficulty == "easy":
        base, exp = random.randint(2, 9), random.randint(2, 3)
        return _new("exponents", difficulty, f"{base}^{exp} = ?", "number", str(base ** exp))
    if difficulty == "medium":
        base, exp = random.randint(-6, 6) or 2, random.randint(2, 3)
        return _new("exponents", difficulty, f"({base})^{exp} = ?", "number", str(base ** exp))
    base, exp = random.choice([2, 3, 4, 5, 10]), random.randint(2, 3)
    # negative exponent -> fraction
    result = Fraction(1, base ** exp)
    return _new("exponents", difficulty, f"{base}^(-{exp}) = ?", "number", f"1/{base ** exp}" if result != 1 else "1")


# ------------------------------------------------------------------ Equations

def gen_one_step_equations(difficulty: str) -> GeneratedProblem:
    rng = {"easy": (1, 15), "medium": (-15, 15), "hard": (-20, 20)}[difficulty]
    op = random.choice(["+", "-", "*", "/"])
    if op in ("+", "-"):
        x_val = random.randint(*rng)
        a = random.randint(*rng)
        b = x_val + a if op == "+" else x_val - a
        question = f"x {op} {a} = {b}"
    elif op == "*":
        a = _nonzero(*rng)
        x_val = random.randint(*rng)
        b = a * x_val
        question = f"{a}x = {b}"
    else:
        a = _nonzero(2, max(rng[1], 2))
        k = random.randint(rng[0], rng[1])
        x_val = a * k
        question = f"x / {a} = {k}"
    return _new("one_step_equations", difficulty, f"Solve for x: {question}", "number", str(x_val))


def gen_two_step_equations(difficulty: str) -> GeneratedProblem:
    rng = {"easy": (1, 10), "medium": (-12, 12), "hard": (-15, 15)}[difficulty]
    a = _nonzero(*rng)
    b = random.randint(*rng)
    if difficulty == "hard":
        c = random.randint(*rng)
        x_val = Fraction(c - b, a)
    else:
        x_val = Fraction(random.randint(*rng))
        c = a * x_val + b
    question = f"{_format_linear(a, b)} = {int(c)}"
    answer = str(x_val.numerator) if x_val.denominator == 1 else f"{x_val.numerator}/{x_val.denominator}"
    return _new("two_step_equations", difficulty, f"Solve for x: {question}", "number", answer)


def gen_multi_step_equations(difficulty: str) -> GeneratedProblem:
    rng = {"easy": (1, 8), "medium": (-10, 10), "hard": (-12, 12)}[difficulty]
    a = _nonzero(*rng)
    b = random.randint(*rng)
    c = random.randint(*rng)
    if difficulty == "hard":
        d = random.randint(*rng)
        x_val = Fraction(d - c - a * b, a)
    else:
        x_val = Fraction(random.randint(*rng))
        d = a * (x_val + b) + c
    inner = _format_linear(1, b)
    question = f"{a}({inner}) {'+' if c >= 0 else '-'} {abs(c)} = {int(d)}"
    answer = str(x_val.numerator) if x_val.denominator == 1 else f"{x_val.numerator}/{x_val.denominator}"
    return _new("multi_step_equations", difficulty, f"Solve for x: {question}", "number", answer)


# --------------------------------------------------------- Graphing & Systems

def gen_slope(difficulty: str) -> GeneratedProblem:
    rng = {"easy": (-10, 10), "medium": (-15, 15), "hard": (-20, 20)}[difficulty]
    x1, x2 = random.randint(*rng), random.randint(*rng)
    while x1 == x2:
        x2 = random.randint(*rng)
    y1, y2 = random.randint(*rng), random.randint(*rng)
    slope = Fraction(y2 - y1, x2 - x1)
    question = f"Find the slope through ({x1}, {y1}) and ({x2}, {y2})."
    answer = str(slope.numerator) if slope.denominator == 1 else f"{slope.numerator}/{slope.denominator}"
    return _new("slope", difficulty, question, "number", answer)


def gen_slope_intercept_form(difficulty: str) -> GeneratedProblem:
    rng = {"easy": (-9, 9), "medium": (-12, 12), "hard": (-15, 15)}[difficulty]
    m = _nonzero(*({"easy": (-5, 5), "medium": (-8, 8), "hard": (-10, 10)}[difficulty]))
    x = random.randint(*rng)
    y = random.randint(*rng)
    b = Fraction(y) - Fraction(m) * Fraction(x)
    question = f"A line has slope {m} and passes through ({x}, {y}). Find b in y = {m}x + b."
    answer = str(b.numerator) if b.denominator == 1 else f"{b.numerator}/{b.denominator}"
    return _new("slope_intercept_form", difficulty, question, "number", answer)


def gen_systems_of_equations(difficulty: str) -> GeneratedProblem:
    rng = {"easy": (-8, 8), "medium": (-10, 10), "hard": (-12, 12)}[difficulty]
    while True:
        x_val, y_val = random.randint(*rng), random.randint(*rng)
        a1, b1 = _nonzero(*rng), _nonzero(*rng)
        a2, b2 = _nonzero(*rng), _nonzero(*rng)
        if a1 * b2 - a2 * b1 != 0:
            break
    c1 = a1 * x_val + b1 * y_val
    c2 = a2 * x_val + b2 * y_val
    eq1 = f"{a1}x {('+' if b1 >= 0 else '-')} {abs(b1)}y = {c1}"
    eq2 = f"{a2}x {('+' if b2 >= 0 else '-')} {abs(b2)}y = {c2}"
    question = f"Solve the system:  {eq1}   and   {eq2}.  Answer as x, y"
    answer = f"{x_val}, {y_val}"
    return _new("systems_of_equations", difficulty, question, "xy_pair", answer)


def gen_factoring_quadratics(difficulty: str) -> GeneratedProblem:
    rng = {"easy": (1, 6), "medium": (-8, 8), "hard": (-10, 10)}[difficulty]
    if difficulty == "easy":
        r1, r2 = random.randint(*rng), random.randint(*rng)
    else:
        r1, r2 = _nonzero(*rng), _nonzero(*rng)
    b = -(r1 + r2)
    c = r1 * r2
    question = f"Solve for x: x^2 {('+' if b >= 0 else '-')} {abs(b)}x {('+' if c >= 0 else '-')} {abs(c)} = 0  (comma-separate both roots)"
    answer = f"{r1}, {r2}"
    return _new("factoring_quadratics", difficulty, question, "root_pair", answer)


# --------------------------------------------------------------- More Foundations

def gen_percentages(difficulty: str) -> GeneratedProblem:
    if difficulty == "easy":
        p = random.choice(range(10, 100, 10))
        n = random.choice(range(10, 201, 10))
        answer = Fraction(p, 100) * n
        question = f"What is {p}% of {n}?"
    elif difficulty == "medium":
        p = random.randint(1, 99)
        n = random.randint(10, 300)
        answer = Fraction(p, 100) * n
        question = f"What is {p}% of {n}?"
    else:
        if random.random() < 0.5:
            whole = random.randint(10, 200)
            part = random.randint(1, whole)
            answer = Fraction(part, whole) * 100
            question = f"{part} is what percent of {whole}?"
        else:
            p = random.choice([10, 20, 25, 50, 75])
            whole = random.randint(1, 20) * 20
            answer = Fraction(whole)
            part = Fraction(p, 100) * whole
            question = f"{part.numerator} is {p}% of what number?"
    ans_str = str(answer.numerator) if answer.denominator == 1 else f"{answer.numerator}/{answer.denominator}"
    return _new("percentages", difficulty, question, "number", ans_str)


def gen_ratios_proportions(difficulty: str) -> GeneratedProblem:
    b = random.randint(2, {"easy": 10, "medium": 15, "hard": 20}[difficulty])
    a = random.randint(1, 15)
    if difficulty == "hard":
        d = random.randint(2, 20)
    else:
        d = b * random.randint(1, 8)
    x_val = Fraction(a * d, b)
    question = f"Solve the proportion: {a}/{b} = x/{d}"
    answer = str(x_val.numerator) if x_val.denominator == 1 else f"{x_val.numerator}/{x_val.denominator}"
    return _new("ratios_proportions", difficulty, question, "number", answer)


# ------------------------------------------------------------- More Equations

def gen_absolute_value_equations(difficulty: str) -> GeneratedProblem:
    rng = {"easy": (1, 10), "medium": (-12, 12), "hard": (-15, 15)}[difficulty]
    b_max = {"easy": 10, "medium": 15, "hard": 20}[difficulty]
    a = random.randint(*rng)
    b = random.randint(1, b_max)  # b > 0 so there are two distinct real solutions
    r1, r2 = -a + b, -a - b
    sign = "+" if a >= 0 else "-"
    question = f"Solve for x: |x {sign} {abs(a)}| = {b}  (comma-separate both solutions)"
    answer = f"{r1}, {r2}"
    return _new("absolute_value_equations", difficulty, question, "root_pair", answer)


def gen_inequalities(difficulty: str) -> GeneratedProblem:
    rng = {"easy": (1, 10), "medium": (-10, 10), "hard": (-12, 12)}[difficulty]
    a = _nonzero(*rng)
    b = random.randint(*rng)
    c = random.randint(*rng)
    op = random.choice(["<", ">", "<=", ">="])
    flipped = {"<": ">", ">": "<", "<=": ">=", ">=": "<="}[op]
    final_op = op if a > 0 else flipped
    rhs = Fraction(c - b, a)
    val_str = str(rhs.numerator) if rhs.denominator == 1 else f"{rhs.numerator}/{rhs.denominator}"
    question = f"Solve for x: {_format_linear(a, b)} {op} {c}   (answer as: x {final_op} ...)"
    answer = f"x {final_op} {val_str}"
    return _new("inequalities", difficulty, question, "inequality", answer)


# ------------------------------------------------------------- More Expressions

def gen_polynomial_add_sub(difficulty: str) -> GeneratedProblem:
    rng = {"easy": (1, 9), "medium": (-9, 9), "hard": (-12, 12)}[difficulty]

    def rand_poly():
        x2 = random.randint(*rng) if random.random() < 0.7 else 0
        x1 = _nonzero(*rng)
        x0 = random.randint(*rng)
        return x2, x1, x0

    def poly_str(poly):
        x2, x1, x0 = poly
        parts = []
        if x2 != 0:
            parts.append(_fmt_term(x2, "x^2", is_first=True))
        if x1 != 0 or not parts:
            parts.append(_fmt_term(x1, "x", is_first=not parts))
        if x0 != 0 or not parts:
            parts.append(_fmt_term(x0, "", is_first=not parts))
        text = "".join(parts).strip()
        return text if text else "0"

    p1, p2 = rand_poly(), rand_poly()
    op = random.choice(["+", "-"])
    a2, a1, a0 = p1
    b2, b1, b0 = p2
    if op == "+":
        r2, r1, r0 = a2 + b2, a1 + b1, a0 + b0
    else:
        r2, r1, r0 = a2 - b2, a1 - b1, a0 - b0

    question = f"Simplify: ({poly_str(p1)}) {op} ({poly_str(p2)})"
    answer = poly_str((r2, r1, r0))
    return _new("polynomial_add_sub", difficulty, question, "linear_expr", answer)


GENERATORS = {
    "integer_arithmetic": gen_integer_arithmetic,
    "order_of_operations": gen_order_of_operations,
    "fractions": gen_fractions,
    "combining_like_terms": gen_combining_like_terms,
    "distributive_property": gen_distributive_property,
    "exponents": gen_exponents,
    "one_step_equations": gen_one_step_equations,
    "two_step_equations": gen_two_step_equations,
    "multi_step_equations": gen_multi_step_equations,
    "slope": gen_slope,
    "slope_intercept_form": gen_slope_intercept_form,
    "systems_of_equations": gen_systems_of_equations,
    "factoring_quadratics": gen_factoring_quadratics,
    "percentages": gen_percentages,
    "ratios_proportions": gen_ratios_proportions,
    "absolute_value_equations": gen_absolute_value_equations,
    "inequalities": gen_inequalities,
    "polynomial_add_sub": gen_polynomial_add_sub,
}


def generate_problem(skill_id: str, difficulty: str) -> GeneratedProblem:
    return GENERATORS[skill_id](difficulty)


# ---------------------------------------------------------------- Answer checking

def _values_equal(a, b) -> bool:
    return simplify(a - b) == 0


def _parse_inequality(text: str):
    match = _INEQUALITY_PATTERN.match(text)
    if not match:
        raise InvalidAnswer(f"expected a form like 'x > 3', got {text!r}")
    op, value_str = match.group(1), match.group(2)
    return op, _safe_parse(value_str)


def check_answer(answer_kind: str, correct_answer: str, student_answer: str) -> bool:
    try:
        if answer_kind == "number":
            return _values_equal(_safe_parse(correct_answer), _safe_parse(student_answer))

        if answer_kind == "linear_expr":
            c = expand(_safe_parse(correct_answer))
            s = expand(_safe_parse(student_answer))
            return simplify(c - s) == 0

        if answer_kind == "xy_pair":
            cx, cy = (p.strip() for p in correct_answer.split(","))
            parts = [p.strip() for p in student_answer.replace("x", "").replace("y", "").replace("=", " ").split(",")]
            if len(parts) != 2:
                return False
            sx, sy = parts
            return _values_equal(_safe_parse(cx), _safe_parse(sx)) and _values_equal(_safe_parse(cy), _safe_parse(sy))

        if answer_kind == "root_pair":
            cr1, cr2 = (p.strip() for p in correct_answer.split(","))
            parts = [p.strip() for p in student_answer.split(",")]
            if len(parts) != 2:
                return False
            sr1, sr2 = (_safe_parse(p) for p in parts)
            c1, c2 = _safe_parse(cr1), _safe_parse(cr2)
            direct = _values_equal(c1, sr1) and _values_equal(c2, sr2)
            swapped = _values_equal(c1, sr2) and _values_equal(c2, sr1)
            return direct or swapped

        if answer_kind == "inequality":
            c_op, c_val = _parse_inequality(correct_answer)
            s_op, s_val = _parse_inequality(student_answer)
            return c_op == s_op and _values_equal(c_val, s_val)
    except Exception:
        return False
    return False
