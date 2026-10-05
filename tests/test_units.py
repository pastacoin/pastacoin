import pytest

from pasta.core.units import UNITS_PER_PASTA, as_units, format_units, to_units


def test_to_units_is_exact():
    assert to_units("1") == UNITS_PER_PASTA
    assert to_units("0.1") == UNITS_PER_PASTA // 10
    assert to_units(" 2.50000001 ") == 250_000_001
    assert to_units(3) == 3 * UNITS_PER_PASTA
    assert to_units("0.00000001") == 1


@pytest.mark.parametrize("bad", ["", "abc", "1.000000001", "nan", "inf"])
def test_to_units_rejects(bad):
    with pytest.raises(ValueError):
        to_units(bad)


def test_format_units():
    assert format_units(150_000_000) == "1.5"
    assert format_units(0) == "0"
    assert format_units(1) == "0.00000001"
    assert format_units(-25_000_000) == "-0.25"
    assert format_units(123_456_789, places=4) == "1.2346"


def test_as_units_is_strict():
    assert as_units(5) == 5
    assert as_units(5.0) == 5
    for bad in (1.5, "5", None, True):
        with pytest.raises(ValueError):
            as_units(bad)
