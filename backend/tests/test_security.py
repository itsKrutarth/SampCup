import datetime as dt

import pytest

from app.core.security import hash_password, token_digest, verify_password
from app.store import Store, _stored


def test_password_hash_round_trip() -> None:
    stored = hash_password("correct horse")
    assert stored.startswith("scrypt$")
    assert verify_password("correct horse", stored)
    assert not verify_password("wrong", stored)
    assert hash_password("correct horse") != stored  # salted


@pytest.mark.parametrize("stored", ["", "nonsense", "bcrypt$1$2$3$aa$bb"])
def test_unknown_hash_formats_never_verify(stored: str) -> None:
    assert not verify_password("anything", stored)


def test_token_digest_is_stable_and_hides_the_token() -> None:
    assert token_digest("abc") == token_digest("abc") != "abc"


def test_rate_counter_counts_per_window(store: Store) -> None:
    assert [store.hit("ip", 10, clock=5) for _ in range(3)] == [1, 2, 3]
    assert store.hit("other-ip", 10, clock=5) == 1
    assert store.hit("ip", 10, clock=12) == 1  # next window


def test_times_must_carry_a_timezone() -> None:
    with pytest.raises(ValueError, match="naive"):
        _stored(dt.datetime(2026, 1, 1))
    assert _stored(1.5) == _stored(1.5)
