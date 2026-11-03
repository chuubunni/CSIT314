"""Forecast, moving average and unusual-day detection for the platform graphs (PM21).
Pure functions: no Flask, no SQL, no numpy (so the site runs on any machine that has Flask).

  moving_average   smooths day-to-day noise
  forecast         next 7 days = straight-line TREND + a "day of the week" effect, with a range
  detect_anomalies flags days that are far from what was normal, allowing for busier weekends
"""
import math
from datetime import timedelta
from statistics import median

Z_95 = 1.96                       # 95% prediction range
ANOMALY_THRESHOLD = 3.0           # how many "normal wobbles" away a day must be to be flagged
MAD_TO_SIGMA = 1.4826             # turns the median absolute deviation into a standard deviation


def moving_average(values, window=7):
    """Trailing average. The first window-1 entries are None (not enough days yet)."""
    result = []
    for i in range(len(values)):
        if i + 1 < window:
            result.append(None)
        else:
            result.append(round(sum(values[i + 1 - window:i + 1]) / window, 2))
    return result


def _fit_line(values):
    """Least-squares straight line through (0, v0), (1, v1) ... -> slope, intercept, mean_t, Sxx."""
    n = len(values)
    mean_t = (n - 1) / 2
    mean_v = sum(values) / n
    sxx = sum((t - mean_t) ** 2 for t in range(n))
    slope = sum((t - mean_t) * (v - mean_v) for t, v in enumerate(values)) / sxx if sxx else 0.0
    return slope, mean_v - slope * mean_t, mean_t, sxx


def _trimmed_mean(items):
    """Average without the single largest value (when there are enough values to spare one)."""
    items = sorted(items)
    if len(items) > 3:
        items = items[:-1]
    return sum(items) / len(items)


def weekday_factors(values, dates, min_days=21, min_per_weekday=3):
    """How much busier or quieter each weekday is than a typical day (1.0 = typical).
    Needs 3 weeks of data, otherwise every factor is 1.0. Returns {0..6: factor} (Monday = 0)."""
    factors = {d: 1.0 for d in range(7)}
    if len(values) < min_days:
        return factors
    overall = _trimmed_mean(values)     # drop the single biggest day, so one wild day cannot distort a weekday's factor
    if overall <= 0:
        return factors
    by_day = {d: [] for d in range(7)}
    for value, date in zip(values, dates):
        by_day[date.weekday()].append(value)
    for day, items in by_day.items():
        if len(items) >= min_per_weekday:
            factors[day] = min(2.5, max(0.4, _trimmed_mean(items) / overall))
    return factors


def forecast(values, dates, horizon=7, min_points=14, max_history=28):
    """The next `horizon` days after the last date, or None if there are fewer than `min_points` days.

    How: fit a straight line (the TREND) to the last `max_history` days, work out how much each
    weekday sits above or below that line (the WEEKDAY EFFECT), and add the two. The range is a
    95% prediction interval: it is wider further into the future and when the data is noisy.
    Counts cannot be negative, so predictions and the lower end are never below 0.
    """
    values, dates = list(values)[-max_history:], list(dates)[-max_history:]
    n = len(values)
    if n < min_points:
        return None
    slope, intercept, mean_t, sxx = _fit_line(values)
    residuals = [v - (intercept + slope * t) for t, v in enumerate(values)]

    # weekday effect = MEDIAN residual of that weekday (needs 2+ days of that weekday); a median is
    # not dragged around by one odd day the way an average is
    by_day = {d: [] for d in range(7)}
    for r, date in zip(residuals, dates):
        by_day[date.weekday()].append(r)
    effect = {d: (median(items) if len(items) >= 2 else 0.0) for d, items in by_day.items()}

    # spread of what is left over (n - 2 because two numbers were fitted)
    leftover = [r - effect[date.weekday()] for r, date in zip(residuals, dates)]
    sigma = math.sqrt(sum(x * x for x in leftover) / max(n - 2, 1))

    out = {'labels': [], 'values': [], 'lower': [], 'upper': []}
    for h in range(1, horizon + 1):
        date = dates[-1] + timedelta(days=h)
        t = n - 1 + h
        mean = max(0.0, intercept + slope * t + effect[date.weekday()])
        # textbook prediction interval for a fitted line: wider the further we are from the data
        spread = Z_95 * sigma * math.sqrt(1 + 1 / n + ((t - mean_t) ** 2) / sxx)
        out['labels'].append(date.isoformat())
        out['values'].append(round(mean, 1))
        out['lower'].append(round(max(0.0, mean - spread), 1))
        out['upper'].append(round(mean + spread, 1))
    return out


def detect_anomalies(values, dates, window=14, min_baseline=7, threshold=ANOMALY_THRESHOLD):
    """Days that are unusually high ('spike') or low ('drop') compared with the days before them.

    1. Remove the weekday effect, so a normal busy Saturday is not flagged.
    2. Compare each day with the MEDIAN of the previous `window` days (one wild day cannot drag
       a median the way it drags an average).
    3. "Normal wobble" = 1.4826 x median absolute deviation, but never less than sqrt(median)
       (counts jump around at least that much by chance) and never less than 1.
    A day is flagged when it is `threshold` normal wobbles away.
    Returns [{'index', 'date', 'value', 'expected', 'kind'}] (index counts from the first day given).
    """
    factors = weekday_factors(values, dates)
    adjusted = [v / factors[d.weekday()] for v, d in zip(values, dates)]
    found = []
    for i in range(min_baseline, len(values)):
        baseline = adjusted[max(0, i - window):i]
        centre = median(baseline)
        mad = median(abs(x - centre) for x in baseline)
        wobble = max(MAD_TO_SIGMA * mad, math.sqrt(max(centre, 1.0)), 1.0)
        z = (adjusted[i] - centre) / wobble
        if abs(z) >= threshold:
            found.append({'index': i, 'date': dates[i].isoformat(), 'value': values[i],
                          'expected': round(centre * factors[dates[i].weekday()], 1),
                          'kind': 'spike' if z > 0 else 'drop'})
    return found


def without_anomalies(values, anomalies):
    """A copy of `values` where each flagged day is replaced by what was expected, so one wild
    day does not tilt the trend line that the forecast is built on."""
    cleaned = list(values)
    for item in anomalies:
        cleaned[item['index']] = item['expected']
    return cleaned
