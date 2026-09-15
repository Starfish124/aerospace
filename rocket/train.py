"""Train PPO on the 2D lander, CPU only. `--eval` reports the soft-landing rate over 100 episodes.
uv run python rocket/train.py            # train, saves rocket/lander_ppo.zip
uv run python rocket/train.py --eval     # evaluate the saved model, print one landing in ASCII
"""
import sys
import time
from pathlib import Path

import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env

from rocket.lander_env import LanderEnv

MODEL = Path(__file__).with_name("lander_ppo.zip")
torch.set_num_threads(4)  # ponytail: share the M4 with the nightly scan


def train(steps=1_000_000):
    env = make_vec_env(LanderEnv, n_envs=8, seed=0)
    if MODEL.exists():  # resume
        model = PPO.load(MODEL, env=env, device="cpu")
    else:
        model = PPO("MlpPolicy", env, n_steps=512, batch_size=512, learning_rate=3e-4, gamma=0.995,
                    ent_coef=0.01, seed=0, device="cpu", verbose=0)
    t0 = time.time()
    best = evaluate(model, episodes=100)[0] if MODEL.exists() else 0.0
    for chunk in range(steps // 100_000):
        model.learn(100_000, reset_num_timesteps=False)
        rate, _ = evaluate(model, episodes=100)
        print(f"{(chunk+1)*100_000:>9,d} steps  {time.time()-t0:5.0f}s  soft landings {rate:.0%}  best {max(best, rate):.0%}", flush=True)
        if rate > best:  # PPO wobbles; keep only the best checkpoint
            best = rate
            model.save(MODEL)
        if best >= 0.92:
            break
    return model


def evaluate(model, episodes=100, render=False):
    env = LanderEnv()
    landed, frames = 0, []
    for ep in range(episodes):
        obs, _ = env.reset(seed=1000 + ep)
        done = False
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, r, done, _, info = env.step(action)
            if render and ep == 0 and env.p.steps % 20 == 0:
                frames.append(env.render())
        landed += info.get("landed", False)
    return landed / episodes, frames


if __name__ == "__main__":
    if "--eval" in sys.argv:
        rate, frames = evaluate(PPO.load(MODEL, device="cpu"), render=True)
        print("\n\n".join(frames))
        print(f"\nsoft landings: {rate:.0%} of 100 episodes")
    else:
        train(int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 1_000_000)
