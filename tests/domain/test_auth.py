from app.domain.auth import hash_password, verify_password


def test_roundtrip():
    stored = hash_password("correct-horse", iterations=1000)
    assert verify_password("correct-horse", stored)


def test_wrong_password_fails():
    stored = hash_password("correct-horse", iterations=1000)
    assert not verify_password("wrong-password", stored)


def test_hash_is_salted_differently_each_time():
    a = hash_password("same-password", iterations=1000)
    b = hash_password("same-password", iterations=1000)
    assert a != b
    assert verify_password("same-password", a)
    assert verify_password("same-password", b)


def test_malformed_stored_value_fails_safely():
    assert not verify_password("anything", "garbage")
