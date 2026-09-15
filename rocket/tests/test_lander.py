import numpy as np
from rocket.lander_env import Physics, LanderEnv


def test_hover_policy_survives_and_burns_fuel():
    p = Physics(); p.reset(np.random.default_rng(0))
    for _ in range(100):
        _, _, done, _ = p.step(1 if p.vy < 0 else 0)
        assert not done
    assert 0 < p.fuel < 1


def test_free_fall_crashes_with_penalty():
    p = Physics(); p.reset(np.random.default_rng(0))
    done = False
    while not done:
        _, r, done, info = p.step(0)
    assert info["landed"] is False and r < -50  # the final step carries the crash penalty


def test_gym_env_contract():
    from stable_baselines3.common.env_checker import check_env
    check_env(LanderEnv(), warn=False)
