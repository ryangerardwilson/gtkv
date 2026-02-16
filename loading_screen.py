"""Matrix-style loading screen."""

from __future__ import annotations

import random

from gi.repository import Gdk, GLib, Gtk  # type: ignore[import-not-found, attr-defined]

from ascii_logo import ASCII_LOGO
from design_constants import colors_for


class LoadingScreen:
    def __init__(self, ui_mode: str) -> None:
        self._ui_mode = ui_mode
        self._min_elapsed = False
        self._ready = False
        self._overlay = Gtk.Overlay()
        self._overlay.set_hexpand(True)
        self._overlay.set_vexpand(True)

        self._container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._container.set_hexpand(True)
        self._container.set_vexpand(True)
        self._container.set_halign(Gtk.Align.FILL)
        self._container.set_valign(Gtk.Align.FILL)

        self._content_holder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._content_holder.set_hexpand(True)
        self._content_holder.set_vexpand(True)
        self._content_holder.set_halign(Gtk.Align.FILL)
        self._content_holder.set_valign(Gtk.Align.FILL)
        self._content_holder.set_visible(False)

        self._overlay.set_child(self._content_holder)
        self._overlay.add_overlay(self._build_loading_panel())
        self._container.append(self._overlay)

        GLib.timeout_add(4000, self._mark_min_elapsed)

    @property
    def container(self) -> Gtk.Widget:
        return self._container

    def attach_content(self, content: Gtk.Widget) -> None:
        for child in list(self._content_holder):
            self._content_holder.remove(child)
        self._content_holder.append(content)

    def finish_when_ready(self) -> None:
        self._ready = True
        self._maybe_hide()

    def _mark_min_elapsed(self) -> bool:
        self._min_elapsed = True
        self._maybe_hide()
        return False

    def _maybe_hide(self) -> None:
        if not (self._min_elapsed and self._ready):
            return
        self._loading_panel.set_visible(False)
        self._content_holder.set_visible(True)

    def _build_loading_panel(self) -> Gtk.Widget:
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        panel.add_css_class("loading-overlay")
        panel.set_halign(Gtk.Align.FILL)
        panel.set_valign(Gtk.Align.FILL)
        panel.set_hexpand(True)
        panel.set_vexpand(True)

        overlay = Gtk.Overlay()
        overlay.set_hexpand(True)
        overlay.set_vexpand(True)

        rain = Gtk.DrawingArea()
        rain.set_hexpand(True)
        rain.set_vexpand(True)
        rain.set_size_request(640, 420)
        rain.set_draw_func(self._draw_matrix)
        overlay.set_child(rain)

        center = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        center.set_halign(Gtk.Align.CENTER)
        center.set_valign(Gtk.Align.CENTER)

        ascii_label = Gtk.Label(label=ASCII_LOGO)
        ascii_label.add_css_class("loading-ascii")
        ascii_label.set_halign(Gtk.Align.CENTER)
        ascii_label.set_justify(Gtk.Justification.CENTER)
        center.append(ascii_label)

        overlay.add_overlay(center)
        panel.append(overlay)

        self._rain_widget = rain
        self._loading_panel = panel
        self._rain_columns: list[dict[str, float]] = []
        GLib.timeout_add(45, self._tick_matrix)
        return panel

    def _tick_matrix(self) -> bool:
        if not self._loading_panel.get_visible():
            return False
        self._rain_widget.queue_draw()
        return True

    def _draw_matrix(self, _area: Gtk.DrawingArea, cr, width: int, height: int) -> None:
        column_count = max(1, width // 14)
        if not self._rain_columns or len(self._rain_columns) != column_count:
            self._rain_columns = []
            for _ in range(column_count):
                self._rain_columns.append(
                    {
                        "y": random.uniform(-height, 0),
                        "speed": random.uniform(8.0, 22.0),
                        "trail": random.randint(4, 10),
                        "delay": random.uniform(0.0, 400.0),
                    }
                )

        palette = colors_for(self._ui_mode)
        bg_rgba = Gdk.RGBA()
        bg_rgba.parse(palette.loading_background)
        cr.set_source_rgba(
            bg_rgba.red, bg_rgba.green, bg_rgba.blue, bg_rgba.alpha
        )
        cr.rectangle(0, 0, width, height)
        cr.fill()

        fg_rgba = Gdk.RGBA()
        fg_rgba.parse(palette.loading_rain_primary)
        dim_rgba = Gdk.RGBA()
        dim_rgba.parse(palette.loading_rain_secondary)

        for idx, drop in enumerate(self._rain_columns):
            x = idx * 14
            if drop["delay"] > 0:
                drop["delay"] -= 45.0
                continue
            y = drop["y"]
            trail = int(drop["trail"])
            for step in range(trail):
                alpha = max(0.15, 0.8 - (step / max(1, trail)))
                cr.set_source_rgba(dim_rgba.red, dim_rgba.green, dim_rgba.blue, alpha)
                cr.rectangle(x, y - (step * 12), 6, 6)
                cr.fill()
            cr.set_source_rgba(fg_rgba.red, fg_rgba.green, fg_rgba.blue, 0.95)
            cr.rectangle(x, y, 6, 6)
            cr.fill()
            drop["y"] = y + drop["speed"]
            if drop["y"] > height + (trail * 12):
                drop["y"] = random.uniform(-height, 0)
                drop["speed"] = random.uniform(8.0, 22.0)
                drop["trail"] = random.randint(4, 10)
                drop["delay"] = random.uniform(0.0, 300.0)
