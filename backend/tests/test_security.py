import pytest

from app.core.security import RateLimiter, hash_password, token_digest, verify_password
from app.db.types import UTCDateTime


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


def test_rate_limiter_allows_a_burst_then_blocks_until_the_window_passes() -> None:
    now = [0.0]
    limiter = RateLimiter(limit=2, window=10, clock=lambda: now[0])
    assert limiter.allow("ip") and limiter.allow("ip")
    assert not limiter.allow("ip")
    assert limiter.allow("other-ip")
    now[0] = 10.0
    assert limiter.allow("ip")
    limiter.reset()
    assert limiter.allow("ip") and limiter.allow("ip")


def test_utc_datetime_refuses_naive_values() -> None:
    from datetime import datetime

    with pytest.raises(ValueError, match="naive"):
        UTCDateTime().process_bind_param(datetime(2026, 1, 1), None)
    assert UTCDateTime().process_bind_param(None, None) is None
    assert UTCDateTime().process_result_value(None, None) is None
