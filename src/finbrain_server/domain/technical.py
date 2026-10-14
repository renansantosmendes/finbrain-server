"""Pure technical-analysis calculations on lists of closing prices."""


def simple_moving_average(
    values: list[float],
    window: int,
) -> float | None:
    """Average of the last ``window`` values.

    Parameters
    ----------
    values : list[float]
        Prices in chronological order.
    window : int
        Number of most recent values averaged.

    Returns
    -------
    float | None
        The average, or ``None`` with fewer than ``window`` values.
    """
    if window < 1 or len(values) < window:
        return None
    return sum(values[-window:]) / window


def exponential_moving_average(
    values: list[float],
    span: int,
) -> list[float]:
    """Exponential moving average with ``alpha = 2 / (span + 1)``.

    It matches ``pandas.Series.ewm(span=span, adjust=False).mean()``.

    Parameters
    ----------
    values : list[float]
        Prices in chronological order.
    span : int
        Span of the average.

    Returns
    -------
    list[float]
        One average per input value.
    """
    alpha = 2 / (span + 1)
    averages = []
    for value in values:
        if not averages:
            averages.append(value)
        else:
            averages.append(alpha * value + (1 - alpha) * averages[-1])
    return averages


def relative_strength_index(
    values: list[float],
    period: int = 14,
) -> float | None:
    """Relative strength index with simple averages of gains and losses.

    Parameters
    ----------
    values : list[float]
        Prices in chronological order.
    period : int
        Number of price changes averaged.

    Returns
    -------
    float | None
        RSI between 0 and 100, or ``None`` without ``period + 1`` prices.

    Example
    -------
    >>> relative_strength_index([float(price) for price in range(1, 20)])
    100.0
    """
    if len(values) < period + 1:
        return None
    changes = [current - previous for previous, current in zip(values, values[1:])]
    recent = changes[-period:]
    average_gain = sum(change for change in recent if change > 0) / period
    average_loss = sum(-change for change in recent if change < 0) / period
    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0
    relative_strength = average_gain / average_loss
    return 100 - 100 / (1 + relative_strength)


def macd(values: list[float]) -> tuple[float | None, float | None]:
    """MACD line (EMA12 - EMA26) and its signal line (EMA9 of the MACD).

    Parameters
    ----------
    values : list[float]
        Prices in chronological order.

    Returns
    -------
    tuple[float | None, float | None]
        Last MACD and signal values, or ``(None, None)`` without data.
    """
    if not values:
        return None, None
    fast = exponential_moving_average(values, 12)
    slow = exponential_moving_average(values, 26)
    line = [fast_value - slow_value for fast_value, slow_value in zip(fast, slow)]
    signal = exponential_moving_average(line, 9)
    return line[-1], signal[-1]


def daily_returns(values: list[float]) -> list[float]:
    """Simple daily returns as fractions (0.01 = 1%).

    Parameters
    ----------
    values : list[float]
        Prices in chronological order.

    Returns
    -------
    list[float]
        One return per pair of consecutive positive prices.
    """
    return [
        current / previous - 1
        for previous, current in zip(values, values[1:])
        if previous > 0
    ]
