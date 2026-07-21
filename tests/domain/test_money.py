from app.domain.money import bhd_to_fils, fils_to_bhd_str, round_half_up_fils


def test_bhd_to_fils():
    assert bhd_to_fils("12.5") == 12_500
    assert bhd_to_fils("12.500") == 12_500
    assert bhd_to_fils(0.001) == 1


def test_fils_to_bhd_str():
    assert fils_to_bhd_str(12_500) == "12.500"
    assert fils_to_bhd_str(1) == "0.001"
    assert fils_to_bhd_str(-2_500) == "-2.500"


def test_round_half_up():
    assert round_half_up_fils(11_538.46) == 11_538
    assert round_half_up_fils(11_538.5) == 11_539
