"""Opinionated helpers for Python image blocks."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import matplotlib.pyplot as plt


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
    x: Sequence[float],
    *y_funcs: Sequence[float] | Callable[[Sequence[float]], Sequence[float]],
    title: str | None = None,
    **named_y: Sequence[float] | Callable[[Sequence[float]], Sequence[float]],
) -> None:
    fig, ax = plt.subplots()
    ax.axhline(y=0, color="k")
    ax.axvline(x=0, color="k")
    ax.grid(True)

    ordered_named = [value for key, value in sorted(named_y.items())]
    for y in list(y_funcs) + ordered_named:
        if callable(y):
            y = y(x)
        ax.plot(x, y)

    if title:
        ax.set_title(title)
    _save_fig(fig)


def _save_fig(fig) -> None:
    renderer = _get_renderer()
    fig.savefig(renderer, dpi=200, bbox_inches="tight", transparent=True)
    plt.close(fig)


def _get_renderer() -> str:
    try:
        return __gtkv__.renderer  # type: ignore[name-defined]
    except Exception as exc:
        raise RuntimeError("__gtkv__.renderer not available") from exc
