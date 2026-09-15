from transit.fetch import fetch
from transit.search import search, Candidate
from transit.vet import vet


def test_pi_men_c_is_known():
    v = vet("TIC261136679", search(fetch("TIC261136679", sectors=1))[0])
    assert v.label == "KNOWN" and "pi Men c" in str(v), str(v)


def test_low_snr_rejected():
    c = Candidate(1.0, 0.0, 0.1, 1e-4, 2.0, 10.0, 5, {"harmonic_delta_log_likelihood": -1, "depth_odd": (1e-4, 1e-4), "depth_even": (1e-4, 1e-4), "depth_phased": (0, 1e-4)})
    assert vet("TIC1", c).label == "REJECTED"


def test_wasp18_b_is_known_despite_real_secondary():
    v = vet("TIC100100827", search(fetch("TIC100100827", sectors=2))[0])
    assert v.label == "KNOWN" and "WASP-18 b" in str(v), str(v)


def test_eclipsing_binary_rejected():
    c = Candidate(1.0, 0.0, 0.1, 1e-2, 50.0, 10.0, 5, {"harmonic_delta_log_likelihood": -1, "depth_odd": (1e-2, 1e-4), "depth_even": (5e-3, 1e-4), "depth_phased": (4e-3, 1e-4)})
    assert vet("TIC1", c).label == "REJECTED"


def test_weak_peak_and_few_transits_rejected():
    st = {"harmonic_delta_log_likelihood": -1, "depth_odd": (1e-3, 1e-4), "depth_even": (1e-3, 1e-4), "depth_phased": (0, 1e-4)}
    assert vet("TIC1", Candidate(1.0, 0.0, 0.1, 1e-3, 20.0, 5.0, 5, st)).label == "REJECTED"   # low sde
    assert vet("TIC1", Candidate(1.0, 0.0, 0.1, 1e-3, 20.0, 10.0, 2, st)).label == "REJECTED"  # 2 transits
    st["harmonic_delta_log_likelihood"] = 5
    assert vet("TIC1", Candidate(1.0, 0.0, 0.1, 1e-3, 20.0, 10.0, 5, st)).label == "REJECTED"  # sine wins


def test_implied_radius():
    from transit.vet import implied_radius_earth
    assert 1.5 < implied_radius_earth(226e-6, 1.10) < 2.5      # Pi Men c is ~2 R_earth
    assert 11 < implied_radius_earth(9474e-6, 1.23) < 15       # WASP-18 b is ~1.2 R_jup
    assert implied_radius_earth(0.053, 1.0) > 22                # 5 % deep on a Sun = a star
