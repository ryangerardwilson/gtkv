"""Opinionated helpers for Python image blocks."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from numbers import Real
from typing import TypeAlias, TypeGuard, cast

import matplotlib.pyplot as plt

XSeries: TypeAlias = Sequence[float]
YValue: TypeAlias = XSeries | float
YCallable: TypeAlias = Callable[[XSeries | float], YValue]
YSeriesArg: TypeAlias = YValue | YCallable


def plot_coord(*coords: tuple[float, float], title: str | None = None) -> None:
    if not coords:
        return
    xs, ys = zip(*coords)
    fig, ax = plt.subplots()
    ax.plot(xs, ys)
    if title:
        ax.set_title(title)
    _save_fig(fig)


def plot_func(
    x: XSeries | float,
    *y_funcs: YSeriesArg,
    title: str | None = None,
    **named_y: YSeriesArg,
) -> None:
    fig, ax = plt.subplots()
    ax.axhline(y=0, color="k")
    ax.axvline(x=0, color="k")
    ax.grid(True)

    ordered_named = [value for key, value in sorted(named_y.items())]
    ys = list(y_funcs) + ordered_named
    if _is_scalar(x):
        _plot_constant_lines(ax, float(x), ys)
    else:
        x_values = cast(XSeries, x)
        for y in ys:
            if callable(y):
                y = y(x_values)
            if _is_scalar(y):
                y = [float(y)] * len(x_values)
            ax.plot(x_values, y)

    if title:
        ax.set_title(title)
    _save_fig(fig)


def _save_fig(fig) -> None:
    renderer = _get_renderer()
    fig.savefig(renderer, dpi=200, bbox_inches="tight", transparent=True)
    plt.close(fig)


def _get_renderer() -> str:
    try:
        return __gvim__.renderer  # type: ignore[name-defined]
    except Exception as exc:
        raise RuntimeError("__gvim__.renderer not available") from exc


def _is_scalar(value: object) -> TypeGuard[Real]:
    return isinstance(value, Real)


def _plot_constant_lines(
    ax,
    x_value: float,
    ys: list[YSeriesArg],
) -> None:
    x_min = x_value - 5.0
    x_max = x_value + 5.0
    x_line = [x_min, x_max]
    for y in ys:
        y_value = y(x_value) if callable(y) else y
        if isinstance(y_value, Sequence) and not _is_scalar(y_value):
            if len(y_value) != 1:
                raise ValueError(
                    "When x is scalar, y values must be scalar or single-item sequences"
                )
            y_value = y_value[0]
        if not _is_scalar(y_value):
            raise ValueError(
                "When x is scalar, each y series must resolve to a scalar value"
            )
        y_line = [float(y_value), float(y_value)]
        ax.plot(x_line, y_line)
