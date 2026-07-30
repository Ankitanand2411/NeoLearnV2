import math
import structlog

log = structlog.get_logger()


# ─── IRT (Item Response Theory) ──────────────────────────────────────────────
#
#  NeoLearn uses a simplified 2-Parameter Logistic (2PL) IRT model:
#
#    P(correct | θ, b) = 1 / (1 + e^(-(θ - b)))
#
#  Where:
#    θ (theta)  = student ability estimate  (range: -3 to +3)
#    b          = item difficulty parameter (range: -3 to +3)
#
#  This is the same statistical model used in GRE, GMAT, and most
#  Computerized Adaptive Testing (CAT) systems.
# ─────────────────────────────────────────────────────────────────────────────

DIFFICULTY_MAP = {
    "easy": -1.0,
    "intermediate": 0.0,
    "hard": 1.5,
}


def select_difficulty(theta: float) -> tuple[str, float]:
    """
    Select the next question difficulty based on student ability (theta).
    Returns (difficulty_label, difficulty_param).
    
    This maximizes Fisher information by choosing the difficulty level
    closest to the student's current ability estimate.
    """
    if theta < -0.5:
        return "easy", DIFFICULTY_MAP["easy"]
    elif theta < 0.8:
        return "intermediate", DIFFICULTY_MAP["intermediate"]
    else:
        return "hard", DIFFICULTY_MAP["hard"]


def irt_probability(theta: float, b: float) -> float:
    """
    Probability that a student with ability θ answers an item with
    difficulty b correctly (2PL model, discrimination=1).
    """
    return 1.0 / (1.0 + math.exp(-(theta - b)))


def update_theta(theta: float, is_correct: bool, b: float) -> float:
    """
    Update student ability estimate using Newton-Raphson approximation.
    
    The update step is proportional to the residual (observed - expected),
    scaled by the Fisher information at the current theta.
    """
    p = irt_probability(theta, b)
    # Fisher information at this point: I(θ) = p * (1 - p)
    info = p * (1 - p)
    if info < 1e-6:
        return theta  # avoid division by zero at extremes

    residual = (1.0 if is_correct else 0.0) - p
    delta = residual / info
    # Clip delta to avoid large jumps
    delta = max(min(delta, 0.5), -0.5)
    new_theta = theta + delta
    # Clamp to realistic range
    return max(min(new_theta, 3.0), -3.0)


def theta_to_mastery(theta: float) -> float:
    """Convert IRT theta (-3 to +3) to mastery percentage (0.0 to 1.0)."""
    return round((theta + 3.0) / 6.0, 4)


def mastery_to_theta(mastery: float) -> float:
    """Convert mastery (0.0–1.0) back to theta (-3 to +3)."""
    return (mastery * 6.0) - 3.0


def compute_accuracy_rate(attempted: int, correct: int) -> float:
    if attempted == 0:
        return 0.0
    return round(correct / attempted, 4)


log.info("mastery_service_loaded", model="2PL IRT")
