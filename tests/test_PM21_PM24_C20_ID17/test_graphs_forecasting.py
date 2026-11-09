"""Pure forecasting maths: moving average, forecast, unusual-day detection."""
import random
from datetime import date, timedelta

from idfinder.controller import forecasting


def days(n, start=date(2026, 9, 1)):
    return [start + timedelta(days=i) for i in range(n)]


def test_moving_average_needs_a_full_window():
    out = forecasting.moving_average([1, 2, 3, 4, 5, 6, 7, 8], 7)
    assert out[:6] == [None] * 6 and out[6] == 4 and out[7] == 5


def test_forecast_needs_14_days():
    assert forecasting.forecast([5] * 13, days(13)) is None
    assert forecasting.forecast([5] * 14, days(14)) is not None


def test_forecast_shape_and_bounds():
    d = days(28)
    values = [10 + i * 0.5 for i in range(28)]
    f = forecasting.forecast(values, d)
    assert len(f['values']) == len(f['lower']) == len(f['upper']) == len(f['labels']) == 7
    assert f['labels'][0] == (d[-1] + timedelta(days=1)).isoformat()
    assert all(lo <= v <= hi for lo, v, hi in zip(f['lower'], f['values'], f['upper']))
    assert all(lo >= 0 for lo in f['lower'])
    assert f['values'][0] > values[0]                       # rising series -> rising forecast


def test_forecast_of_falling_series_is_never_negative():
    f = forecasting.forecast([max(0, 30 - 2 * i) for i in range(28)], days(28))
    assert min(f['lower']) >= 0 and min(f['values']) >= 0


def test_planted_spike_is_flagged_and_weekend_lift_is_not():
    rng = random.Random(3)
    d = days(42)
    values = [round(20 * (1.5 if x.weekday() >= 5 else 1) + rng.gauss(0, 2)) for x in d]
    values[30] = 120
    found = forecasting.detect_anomalies(values, d)
    assert [a['index'] for a in found] == [30] and found[0]['kind'] == 'spike'
    assert not [a for a in forecasting.detect_anomalies(values[:30], d[:30])]


def test_flat_series_with_zero_spread_does_not_divide_by_zero():
    d = days(30)
    assert forecasting.detect_anomalies([5] * 30, d) == []
    values = [5] * 30
    values[-1] = 6                                           # a tiny change must not count as unusual
    assert forecasting.detect_anomalies(values, d) == []


def test_not_enough_baseline_flags_nothing():
    assert forecasting.detect_anomalies([1, 1, 1, 100], days(4)) == []


def test_without_anomalies_replaces_only_flagged_days():
    values = [10] * 20 + [200] + [10] * 5
    d = days(len(values))
    found = forecasting.detect_anomalies(values, d)
    cleaned = forecasting.without_anomalies(values, found)
    assert cleaned[20] < 50 and cleaned[:20] == values[:20] and values[20] == 200


def test_a_strong_regular_weekend_peak_is_not_unusual():
    rng = random.Random(5)
    d = days(56)
    values = [round(20 * (3 if x.weekday() >= 5 else 1) + rng.gauss(0, 2)) for x in d]
    assert forecasting.detect_anomalies(values, d) == []
