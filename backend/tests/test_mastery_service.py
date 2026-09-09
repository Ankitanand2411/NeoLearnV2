"""
Tests for the IRT helpers in app.services.mastery_service.

These are pure functions, so the tests are fast and deterministic. The most
important one is `test_newton_step_was_always_clipped`, which pins down the bug
that motivated the EAP rewrite: the legacy update moved θ by exactly ±0.5 for
every interior θ, so the quiz could not tell a lucky guess from real mastery.
"""

import math

import pytest

from app.services.mastery_service import (
    DIFFICULTY_MAP,
    THETA_MAX,
    THETA_MIN,
    irt_probability,
    mastery_to_theta,
    select_difficulty,
    theta_to_mastery,
    update_theta,
    update_theta_eap,
    update_theta_newton,
)

INTERIOR_THETAS = [t / 10 for t in range(-24, 25)]  # -2.4 … 2.4


# ─── Item response function ───────────────────────────────────────────────────

def test_probability_is_half_when_ability_equals_difficulty():
    assert irt_probability(0.0, 0.0) == pytest.approx(0.5)
    assert irt_probability(1.5, 1.5) == pytest.approx(0.5)


def test_probability_increases_with_ability_and_decreases_with_difficulty():
    assert irt_probability(1.0, 0.0) > irt_probability(0.0, 0.0) > irt_probability(-1.0, 0.0)
    assert irt_probability(0.0, -1.0) > irt_probability(0.0, 0.0) > irt_probability(0.0, 1.5)


def test_discrimination_sharpens_the_curve():
    # Higher `a` pushes probabilities further from 0.5 on either side of b.
    assert irt_probability(1.0, 0.0, a=2.0) > irt_probability(1.0, 0.0, a=1.0)
    assert irt_probability(-1.0, 0.0, a=2.0) < irt_probability(-1.0, 0.0, a=1.0)


def test_default_model_is_rasch_symmetric():
    # Rasch: P(θ, b) + P(b, θ) == 1  because the logistic is odd around b.
    for theta in INTERIOR_THETAS:
        assert irt_probability(theta, 0.7) + irt_probability(0.7, theta) == pytest.approx(1.0)


# ─── Difficulty selection ─────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("theta", "label"),
    [(-3.0, "easy"), (-0.51, "easy"), (-0.5, "intermediate"), (0.79, "intermediate"), (0.8, "hard"), (3.0, "hard")],
)
def test_select_difficulty_bands(theta, label):
    got_label, b = select_difficulty(theta)
    assert got_label == label
    assert b == DIFFICULTY_MAP[label]


# ─── Mastery ⇄ theta ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("theta", [-3.0, -1.2, 0.0, 0.75, 3.0])
def test_mastery_theta_round_trip(theta):
    assert mastery_to_theta(theta_to_mastery(theta)) == pytest.approx(theta, abs=1e-3)


def test_mastery_is_clamped_to_unit_interval():
    assert theta_to_mastery(-10) == 0.0
    assert theta_to_mastery(10) == 1.0
    assert mastery_to_theta(2.0) == THETA_MAX
    assert mastery_to_theta(-1.0) == THETA_MIN


# ─── EAP update (current behaviour) ───────────────────────────────────────────

@pytest.mark.parametrize("theta", INTERIOR_THETAS)
@pytest.mark.parametrize("b", DIFFICULTY_MAP.values())
def test_eap_moves_in_the_right_direction(theta, b):
    assert update_theta(theta, True, b) > theta
    assert update_theta(theta, False, b) < theta


@pytest.mark.parametrize("theta", [-3.0, -2.9, 2.9, 3.0])
def test_eap_stays_within_bounds(theta):
    for b in DIFFICULTY_MAP.values():
        for correct in (True, False):
            assert THETA_MIN <= update_theta(theta, correct, b) <= THETA_MAX


def test_eap_step_scales_with_surprise():
    # A weak student (θ=-1) getting a HARD item right is surprising → big jump.
    surprising = update_theta(-1.0, True, DIFFICULTY_MAP["hard"]) - (-1.0)
    # A strong student (θ=1) getting an EASY item right is expected → small nudge.
    expected = update_theta(1.0, True, DIFFICULTY_MAP["easy"]) - 1.0
    assert surprising > 2 * expected > 0


def test_eap_step_is_not_constant():
    steps = {round(update_theta(t, True, 0.0) - t, 4) for t in INTERIOR_THETAS}
    assert len(steps) > 5, "an adaptive update must not move by a fixed amount"


def test_eap_posterior_sd_is_positive_and_below_prior():
    _, sd = update_theta_eap(0.0, True, 0.0, prior_sd=1.0)
    assert 0.0 < sd < 1.0  # observing data can only reduce uncertainty


def test_eap_is_symmetric_for_rasch():
    # Rasch symmetry: being right on b when θ=0 mirrors being wrong on -b.
    up = update_theta(0.0, True, 0.5)
    down = update_theta(0.0, False, -0.5)
    assert up == pytest.approx(-down, abs=1e-9)


# ─── Legacy Newton update (kept to document the bug) ──────────────────────────

@pytest.mark.parametrize("theta", INTERIOR_THETAS)
@pytest.mark.parametrize("b", DIFFICULTY_MAP.values())
def test_newton_step_was_always_clipped(theta, b):
    """
    For a single Bernoulli response the Newton step is (y-p)/(p(1-p)) whose
    magnitude is 1/(1-p) or 1/p ≥ 1, so the ±0.5 clip always wins. This test
    exists to prove why `update_theta` no longer uses it.
    """
    assert update_theta_newton(theta, True, b) - theta == pytest.approx(0.5)
    assert update_theta_newton(theta, False, b) - theta == pytest.approx(-0.5)


def test_newton_and_eap_agree_on_direction_but_not_magnitude():
    theta, b = -1.0, DIFFICULTY_MAP["hard"]
    newton = update_theta_newton(theta, True, b) - theta
    eap = update_theta(theta, True, b) - theta
    assert math.copysign(1, newton) == math.copysign(1, eap)
    assert newton != pytest.approx(eap)
