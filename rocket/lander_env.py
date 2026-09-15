"""2D rocket lander as a gymnasium environment. Readable physics, no Box2D.
State: x, y, vx, vy, angle, angular velocity, fuel fraction (7 floats, all roughly [-1, 1]).
Actions: 0 nothing, 1 main engine, 2 left thruster, 3 right thruster.
Reward: shaped toward the pad, big bonus for a soft upright landing, big penalty for a crash."""
import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError:  # the env is importable without gymnasium for the physics self-check
    gym = None

G = 1.62           # moon gravity, m/s^2: slow enough to learn, still a real number
DT = 0.05
MAIN = 6.0         # main engine acceleration, m/s^2 (thrust/weight ~ 3.7)
SIDE = 0.6         # side thruster torque as angular acceleration, rad/s^2
SIDE_PUSH = 0.4    # side thrusters also push sideways a little
FUEL_PER_MAIN, FUEL_PER_SIDE = 0.0015, 0.0003
WORLD_W, WORLD_H = 20.0, 20.0   # m; pad is at x=0, y=0
MAX_STEPS = 600
SOFT_V, SOFT_ANGLE = 1.0, 0.25  # m/s, rad: what counts as a soft landing


class Physics:
    """The lander without gymnasium. `step` returns (obs, reward, terminated, info)."""

    def reset(self, rng):
        self.x = rng.uniform(-6, 6)
        self.y = rng.uniform(12, 16)
        self.vx = rng.uniform(-1, 1)
        self.vy = rng.uniform(-1, 0)
        self.angle = rng.uniform(-0.3, 0.3)
        self.w = 0.0
        self.fuel = 1.0
        self.steps = 0
        self.prev_shaping = self._shaping()
        return self.obs()

    def obs(self):
        return np.array([self.x / 10, self.y / 10, self.vx / 5, self.vy / 5, self.angle, self.w, self.fuel], dtype=np.float32)

    def _shaping(self):
        # closer, slower, more upright = better. Same idea as the classic LunarLander shaping.
        # Scale matters: at 1x the agent learned to hover forever (descending risked -100 for ~4 points).
        return -10 * (np.hypot(self.x, self.y) + np.hypot(self.vx, self.vy) + 3 * abs(self.angle))

    def step(self, a):
        ax, ay, aw = 0.0, -G, 0.0
        if a == 1 and self.fuel > 0:
            ax += -MAIN * np.sin(self.angle); ay += MAIN * np.cos(self.angle); self.fuel -= FUEL_PER_MAIN
        elif a == 2 and self.fuel > 0:
            aw += SIDE; ax += SIDE_PUSH * np.cos(self.angle); self.fuel -= FUEL_PER_SIDE
        elif a == 3 and self.fuel > 0:
            aw -= SIDE; ax -= SIDE_PUSH * np.cos(self.angle); self.fuel -= FUEL_PER_SIDE
        self.fuel = max(self.fuel, 0.0)
        self.vx += ax * DT; self.vy += ay * DT; self.w += aw * DT
        self.x += self.vx * DT; self.y += self.vy * DT; self.angle += self.w * DT
        self.steps += 1

        shaping = self._shaping()
        reward = shaping - self.prev_shaping - (0.3 if a == 1 else 0.03 if a else 0) - 0.1  # -0.1/step: hovering is not free
        self.prev_shaping = shaping
        terminated, info = False, {}
        if self.y <= 0:
            terminated = True
            v = np.hypot(self.vx, self.vy)
            soft = v < SOFT_V and abs(self.angle) < SOFT_ANGLE and abs(self.x) < 2.0
            info["landed"] = bool(soft)
            # Graded, not binary: a binary +-100 is a cliff and the agent learned to hover above it forever.
            reward += 100 if soft else float(np.clip(100 - 40 * v - 100 * abs(self.angle) - 15 * abs(self.x), -100, 100))
        elif abs(self.x) > WORLD_W / 2 or self.y > WORLD_H:
            terminated = True
            info["landed"] = False
            reward -= 100
        elif self.steps >= MAX_STEPS:  # ran out of time: no crash penalty, or hovering looks as good as trying
            terminated = True
            info["landed"] = False
        return self.obs(), float(reward), terminated, info


if gym is not None:
    class LanderEnv(gym.Env):
        metadata = {"render_modes": ["ansi"]}

        def __init__(self):
            self.p = Physics()
            self.observation_space = spaces.Box(-np.inf, np.inf, (7,), np.float32)
            self.action_space = spaces.Discrete(4)

        def reset(self, seed=None, options=None):
            super().reset(seed=seed)
            return self.p.reset(self.np_random), {}

        def step(self, action):
            obs, r, term, info = self.p.step(int(action))
            return obs, r, term, False, info

        def render(self):
            """One line: where the lander is, ASCII, for the terminal (ADR-005)."""
            p = self.p
            row = int(np.clip((WORLD_H - p.y) / WORLD_H * 10, 0, 9))
            col = int(np.clip((p.x + WORLD_W / 2) / WORLD_W * 40, 0, 39))
            lines = [[" "] * 40 for _ in range(10)]
            lines[9][18:22] = list("====")
            lines[row][col] = "^" if abs(p.angle) < 0.3 else "/" if p.angle > 0 else "\\"
            return "\n".join("".join(l) for l in lines)


if __name__ == "__main__":  # self-check: physics alone, a hovering policy must not crash immediately
    ph = Physics(); rng = np.random.default_rng(0); ph.reset(rng)
    for _ in range(100):
        _, _, done, _ = ph.step(1 if ph.vy < 0 else 0)
        assert not done
    assert 0 < ph.fuel < 1 and ph.y > 0
    print("physics ok: hover for 100 steps, fuel left", round(ph.fuel, 3))
