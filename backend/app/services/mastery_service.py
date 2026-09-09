"""
Item Response Theory (IRT) helpers for the adaptive quiz.

Model
─────
    P(correct | θ, b, a) = 1 / (1 + e^(-a(θ - b)))

    θ (theta)  student ability, kept in [-3, 3]
    b          item difficulty: the θ at which P = 0.5
    a          item discrimination: how sharply P rises around b

With a = 1 for every item this is the one-parameter logistic / Rasch model.
It only becomes a genuine 2PL model when items carry calibrated, item-specific
`a` values. NeoLearn currently uses a = 1 everywhere (`DEFAULT_DISCRIMINATION`),
so the honest label is "Rasch (1PL)"; the `a` argument exists so per-item
discrimination can be added without touching callers.

Ability update
──────────────
The original implementation took a single Newton–Raphson step on the
log-likelihood of ONE response and clipped it to ±0.5. For a single Bernoulli
observation the raw step is  (y - p) / (p(1 - p)) , whose magnitude is
1/(1-p) or 1/p, i.e. always ≥ 1, so the clip always dominated and every update
was exactly ±0.5 regardless of how surprising the response was
(`update_theta_newton` is kept below for tests and comparison).

`update_theta` now uses an Expected-A-Posteriori (EAP) estimate on a grid:
prior N(θ_prev, PRIOR_SD²) × likelihood of the observed response, then the
posterior mean. A correct answer on a hard item moves θ a lot; a correct answer
on an item the student was already expected to get right moves it a little.
The posterior standard deviation is also returned by `update_theta_eap` so a
future UI can show confidence.
"""

import math

import structlog

log = structlog.get_logger()

THETA_MIN, THETA_MAX = -3.0, 3.0
DEFAULT_DISCRIMINATION = 1.0

# Standard deviation of the prior placed on the previous θ before each update.
# Smaller = more conservative updates. 1.0 gives steps of roughly 0.1–0.6.
PRIOR_SD = 1.0

# Grid used for the EAP integral. It deliberately extends well past the
# reporting range [-3, 3]: integrating a N(θ, 1) prior over a grid cut off at
# ±3 would drop tail mass on one side and bias the posterior mean toward 0,
# which near the edges can exceed a small legitimate update. The mean is
# clamped to [-3, 3] only after integration. 241 points cost microseconds.
_GRID_STEP = 0.05
_GRID_MIN, _GRID_MAX = -6.0, 6.0
_THETA_GRID = [_GRID_MIN + i * _GRID_STEP for i in range(int((_GRID_MAX - _GRID_MIN) / _GRID_STEP) + 1)]

DIFFICULTY_MAP = {
    "easy": -1.0,
    "intermediate": 0.0,
    "hard": 1.5,
}


def select_difficulty(theta: float) -> tuple[str, float]:
    """
    Pick the next question's difficulty band from ability θ.

    Fisher information for a logistic item peaks when b = θ, so we choose the
    band whose b is nearest to θ. Returns (label, b).
    """
    if theta < -0.5:
        return "easy", DIFFICULTY_MAP["easy"]
    elif theta < 0.8:
        return "intermediate", DIFFICULTY_MAP["intermediate"]
    else:
        return "hard", DIFFICULTY_MAP["hard"]


def irt_probability(theta: float, b: float, a: float = DEFAULT_DISCRIMINATION) -> float:
    """Probability that a student with ability θ answers item (b, a) correctly."""
    return 1.0 / (1.0 + math.exp(-a * (theta - b)))


def _clamp(theta: float) -> float:
    return max(min(theta, THETA_MAX), THETA_MIN)


def update_theta_eap(
    theta: float,
    is_correct: bool,
    b: float,
    a: float = DEFAULT_DISCRIMINATION,
    prior_sd: float = PRIOR_SD,
) -> tuple[float, float]:
    """
    Bayesian update of θ from one response. Returns (posterior_mean, posterior_sd).

    posterior(θ) ∝ N(θ; θ_prev, prior_sd²) · P(y | θ, b, a)
    """
    y = 1.0 if is_correct else 0.0
    weights: list[float] = []
    for g in _THETA_GRID:
        prior = math.exp(-0.5 * ((g - theta) / prior_sd) ** 2)
        p = irt_probability(g, b, a)
        likelihood = p if y else (1.0 - p)
        weights.append(prior * likelihood)

    total = sum(weights)
    if total <= 0.0:  # numerically impossible for finite inputs, but stay safe
        return _clamp(theta), prior_sd

    mean = sum(w * g for w, g in zip(weights, _THETA_GRID, strict=True)) / total
    var = sum(w * (g - mean) ** 2 for w, g in zip(weights, _THETA_GRID, strict=True)) / total
    return _clamp(mean), math.sqrt(max(var, 0.0))


def update_theta(theta: float, is_correct: bool, b: float, a: float = DEFAULT_DISCRIMINATION) -> float:
    """Update ability after one response (EAP). Kept as the public entry point."""
    new_theta, _ = update_theta_eap(theta, is_correct, b, a)
    return new_theta


def update_theta_newton(theta: float, is_correct: bool, b: float) -> float:
    """
    Legacy single-step Newton–Raphson update, clipped to ±0.5.

    Retained only for comparison and tests: for one response the raw step is
    always ≥ 1 in magnitude, so this returns θ ± 0.5 for every interior θ.
    """
    p = irt_probability(theta, b)
    info = p * (1 - p)
    if info < 1e-6:
        return theta
    residual = (1.0 if is_correct else 0.0) - p
    delta = residual / info
    delta = max(min(delta, 0.5), -0.5)
    return _clamp(theta + delta)


def theta_to_mastery(theta: float) -> float:
    """Map θ ∈ [-3, 3] linearly to mastery ∈ [0, 1]."""
    return round((_clamp(theta) + 3.0) / 6.0, 4)


def mastery_to_theta(mastery: float) -> float:
    """Inverse of theta_to_mastery."""
    return _clamp((mastery * 6.0) - 3.0)


def compute_accuracy_rate(attempted: int, correct: int) -> float:
    if attempted == 0:
        return 0.0
    return round(correct / attempted, 4)


log.info("mastery_service_loaded", model="Rasch (1PL) IRT with EAP update")
