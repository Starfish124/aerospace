"""Staged ascent to orbit: rocket equation for the ideal budget, then a 2D gravity-turn flight
with gravity and drag losses so the numbers are the ones a real launch sees.
Units: kg, m, s, N. Earth is a sphere, atmosphere is exponential. Euler steps of DT."""
from dataclasses import dataclass
from math import atan2, cos, exp, hypot, log, sin, radians, degrees

G0 = 9.80665
MU = 3.986004418e14      # m^3/s^2
R_EARTH = 6_371_000.0
RHO0, H_SCALE = 1.225, 8_500.0   # kg/m^3, m
DT = 0.1


@dataclass
class Stage:
    dry: float
    prop: float
    thrust: float   # N (vacuum; sea-level is derived from isp_sl/isp_vac)
    isp_vac: float  # s
    isp_sl: float | None = None

    @property
    def mdot(self):
        return self.thrust / (self.isp_vac * G0)

    def isp(self, rho):  # linear blend between sea level and vacuum by air density
        sl = self.isp_sl or self.isp_vac
        return sl + (self.isp_vac - sl) * (1 - rho / RHO0)


@dataclass
class Vehicle:
    stages: list[Stage]
    payload: float
    cd: float = 0.3
    area: float = 10.5  # m^2, 3.66 m diameter

    def mass_at(self, i, burned):
        return self.payload + sum(s.dry + s.prop for s in self.stages[i:]) - burned

    def ideal_dv(self):
        """Rocket equation per stage, vacuum Isp. What you'd get with no gravity, no air."""
        out = []
        for i, s in enumerate(self.stages):
            m0 = self.mass_at(i, 0)
            out.append(s.isp_vac * G0 * log(m0 / (m0 - s.prop)))
        return out


@dataclass
class Flight:
    t: float; alt: float; speed: float; gamma_deg: float
    dv_ideal: float; gravity_loss: float; drag_loss: float; steering_loss: float
    orbit: bool
    log: list

    def __str__(self):
        return (f"t={self.t:.0f}s alt={self.alt/1e3:.0f} km v={self.speed:.0f} m/s "
                f"gamma={self.gamma_deg:.1f}°  ideal dv {self.dv_ideal:.0f}  "
                f"losses: gravity {self.gravity_loss:.0f} drag {self.drag_loss:.0f} steering {self.steering_loss:.0f}  "
                f"{'ORBIT' if self.orbit else 'no orbit'}")


def fly(v: Vehicle, kick_deg=2.0, kick_speed=60.0, target_alt=200e3) -> Flight:
    """Stage 1: vertical climb, one small pitch kick at kick_speed, then thrust along velocity (gravity turn).
    Upper stage: thrust near-horizontal, pitched up or down to hold the climb rate that reaches target_alt.
    Stops when circular speed for the current altitude is reached: that is orbit.
    ponytail: proportional altitude-hold, not optimal guidance; good enough to make insertion robust to kick_deg."""
    x, y = 0.0, R_EARTH          # 2D, launch from the pole of a circle, +y up
    vx, vy = 0.0, 0.0
    t = 0.0
    dv = gl = dl = sl = 0.0
    kicked = False
    log = []
    for i, s in enumerate(v.stages):
        burned = 0.0
        while burned < s.prop:
            r = hypot(x, y)
            alt = r - R_EARTH
            rho = RHO0 * exp(-max(alt, 0) / H_SCALE)
            m = v.mass_at(i, burned)
            g = MU / r**2
            speed = hypot(vx, vy)
            up = (x / r, y / r)
            # thrust direction
            if speed < kick_speed:
                d = up
            elif not kicked:
                kicked = True
                a = radians(kick_deg)
                d = (up[0] * cos(a) + up[1] * sin(a), -up[0] * sin(a) + up[1] * cos(a))  # tilt "east" (clockwise)
                vx, vy = speed * d[0], speed * d[1]
            elif i == 0:
                d = (vx / speed, vy / speed)
            else:  # upper stage: hold a climb rate towards target_alt
                vr = vx * up[0] + vy * up[1]
                want_vr = max(-50.0, min(50.0, (target_alt - alt) / 100.0))
                pitch = radians(max(-30.0, min(30.0, (want_vr - vr) * 0.3)))
                east = (up[1], -up[0])
                d = (east[0] * cos(pitch) + up[0] * sin(pitch), east[1] * cos(pitch) + up[1] * sin(pitch))
            thrust = s.mdot * s.isp(rho) * G0
            drag = 0.5 * rho * speed**2 * v.cd * v.area
            ax = thrust / m * d[0] - g * up[0] - (drag / m) * (vx / speed if speed else 0)
            ay = thrust / m * d[1] - g * up[1] - (drag / m) * (vy / speed if speed else 0)
            vx += ax * DT; vy += ay * DT
            x += vx * DT; y += vy * DT
            burned += s.mdot * DT
            t += DT
            # bookkeeping of where the delta-v went
            radial_v = (vx * up[0] + vy * up[1])
            sin_gamma = radial_v / speed if speed else 1.0
            dv += thrust / m * DT
            gl += g * sin_gamma * DT
            dl += drag / m * DT
            sl += thrust / m * (1 - (d[0] * vx + d[1] * vy) / speed) * DT if speed else 0
            if int(t * 10) % 100 == 0:
                log.append((round(t), round(alt / 1e3), round(speed)))
            v_circ = (MU / r) ** 0.5
            if i == len(v.stages) - 1 and speed >= v_circ and alt > target_alt * 0.5:
                break
    r = hypot(x, y); alt = r - R_EARTH; speed = hypot(vx, vy)
    gamma = degrees(atan2(vx * x / r + vy * y / r, hypot(vx * y / r - vy * x / r, 0)))
    return Flight(t, alt, speed, gamma, dv, gl, dl, abs(sl), speed >= (MU / r) ** 0.5 * 0.98 and alt > 150e3, log)


# Public Falcon 9 Block 5 numbers (SpaceX user's guide + press), expendable to LEO.
FALCON9 = Vehicle(
    stages=[
        Stage(dry=25_600, prop=395_700, thrust=8_227_000, isp_vac=311, isp_sl=282),  # 9 Merlin 1D
        Stage(dry=3_900, prop=92_670, thrust=981_000, isp_vac=348),                  # 1 Merlin Vacuum
    ],
    payload=22_800 + 1_900,  # payload + fairing (kept for simplicity)
)

if __name__ == "__main__":
    print("ideal dv per stage:", [round(d) for d in FALCON9.ideal_dv()], "total", round(sum(FALCON9.ideal_dv())))
    f = fly(FALCON9)
    print(f)
    for row in f.log[::6]:
        print("  t=%4ds  alt=%4d km  v=%5d m/s" % row)
