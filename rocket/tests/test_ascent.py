from dataclasses import replace
from rocket.ascent import FALCON9, fly, MU, R_EARTH


def test_falcon9_ideal_budget_matches_public_figure():
    # Falcon 9 to LEO needs ~9.0-9.3 km/s ideal; ours from public stage numbers
    assert 8_500 < sum(FALCON9.ideal_dv()) < 9_500


def test_falcon9_reaches_orbit_with_16t():
    f = fly(replace(FALCON9, payload=16_000), kick_deg=2.0)
    v_circ = (MU / (R_EARTH + f.alt)) ** 0.5
    assert f.orbit and f.alt > 150e3 and abs(f.speed - v_circ) / v_circ < 0.02, str(f)


def test_losses_account_for_every_metre_per_second():
    f = fly(replace(FALCON9, payload=16_000), kick_deg=2.0)
    delivered = f.dv_ideal - f.gravity_loss - f.drag_loss - f.steering_loss
    assert abs(delivered - f.speed) / f.speed < 0.02, (delivered, f.speed)
