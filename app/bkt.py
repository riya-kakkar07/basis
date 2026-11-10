"""Bayesian Knowledge Tracing (BKT).

Classic two-state hidden Markov model of skill mastery (Corbett & Anderson,
1995). The student's mastery of a skill is a latent binary variable L in
{known, unknown}; we never observe it directly, only noisy evidence through
whether they answer a problem correctly.

Four parameters per skill:
    p_init     P(L0)  - prior probability the skill is already mastered
    p_transit  P(T)   - probability of moving unknown -> known after one
                         practice opportunity (i.e. the "learning rate")
    p_guess    P(G)   - probability of answering correctly while unknown
    p_slip     P(S)   - probability of answering incorrectly while known

Each observed answer updates the mastery estimate in two stages:

1. Bayesian update ("evidence" step) - revise P(L) using Bayes' rule given
   whether the response was correct, via the observation model
       P(correct | known)   = 1 - p_slip
       P(correct | unknown) = p_guess
2. Learning transit - account for the chance the student learned something
   from having just attempted the problem, regardless of whether they got
   it right.

Guess/slip are allowed to vary with the difficulty of the item the student
was actually given (an extension sometimes called KT-IDEM: harder items are
less guessable but more slip-prone) - the induce/transit math stays exactly
the above, just parameterised per (skill, difficulty).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BKTParams:
    p_init: float
    p_transit: float
    p_guess: float
    p_slip: float

    def __post_init__(self) -> None:
        for name in ("p_init", "p_transit", "p_guess", "p_slip"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name}={value} must be a probability in [0, 1]")


def posterior_mastery(prior_mastery: float, correct: bool, params: BKTParams) -> float:
    """Bayes' rule: P(mastered | observed response), before the learning transit."""
    p = prior_mastery
    if correct:
        numerator = p * (1 - params.p_slip)
        denominator = numerator + (1 - p) * params.p_guess
    else:
        numerator = p * params.p_slip
        denominator = numerator + (1 - p) * (1 - params.p_guess)

    if denominator <= 0:
        return p
    return numerator / denominator


def apply_learning_transit(posterior: float, params: BKTParams) -> float:
    """P(L_{n+1}) after the chance to learn that comes with every attempt."""
    return posterior + (1 - posterior) * params.p_transit


def update_mastery(prior_mastery: float, correct: bool, params: BKTParams) -> tuple[float, float]:
    """One full BKT step. Returns (posterior_before_transit, mastery_after_transit)."""
    posterior = posterior_mastery(prior_mastery, correct, params)
    updated = apply_learning_transit(posterior, params)
    return posterior, updated


def predict_correct(mastery: float, params: BKTParams) -> float:
    """P(next response correct), marginalising over the latent mastery state."""
    return mastery * (1 - params.p_slip) + (1 - mastery) * params.p_guess
