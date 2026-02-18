"""Design tokens for UI colors and font sizes."""

from __future__ import annotations


class colors:
    """Theme-aware UI color tokens."""

    class dark:
        """Dark-mode palette."""

        # Base GTK text and heading colors (style.css block text)
        block_text = "#d7d7d7"
        block_title = "#e6e6e6"
        block_h1 = "#dedede"
        block_h2 = "#d9d9d9"
        block_h3 = "#d4d4d4"
        block_h4 = "#d0d0d0"
        block_h5 = "#cccccc"
        block_h6 = "#c8c8c8"
        block_toc = "#bfbfbf"
        app_background = "rgba(0, 0, 0, 0.5)"

        # Inline image label text in GTK
        block_image_label = "#cfcfcf"

        # Selection highlight for the active block (GTK)
        block_selected_shadow = "rgba(0, 0, 0, 0.3)"
        block_selected_background = "rgba(24, 24, 24, 0.85)"

        # Help overlay panel (GTK)
        help_panel_background = "rgba(16, 16, 16, 0.92)"
        help_panel_border = "rgba(255, 255, 255, 0.08)"
        help_title = "#e6e6e6"
        help_body = "#cfcfcf"

        # TOC drill overlay (GTK)
        toc_panel_background = "rgba(12, 12, 12, 0.94)"
        toc_panel_border = "rgba(255, 255, 255, 0.08)"
        toc_panel_shadow = "rgba(0, 0, 0, 0.45)"
        toc_title = "#e6e6e6"
        toc_hint = "#a9a9a9"
        toc_row_selected_background = "rgba(40, 40, 40, 0.8)"
        toc_row_selected_border = "rgba(255, 255, 255, 0.06)"
        toc_row_label = "#d2d2d2"
        toc_empty = "#8f8f8f"

        # Vault overlay (GTK)
        vault_panel_background = "rgba(12, 12, 12, 0.94)"
        vault_panel_border = "rgba(255, 255, 255, 0.08)"
        vault_panel_shadow = "rgba(0, 0, 0, 0.45)"
        vault_title = "#e6e6e6"
        vault_subtitle = "#a9a9a9"
        vault_hint = "#a9a9a9"
        vault_row_selected_background = "rgba(40, 40, 40, 0.8)"
        vault_row_selected_border = "rgba(255, 255, 255, 0.06)"
        vault_row_label = "#d2d2d2"
        vault_empty = "#8f8f8f"
        vault_entry_background = "rgba(20, 20, 20, 0.9)"
        vault_entry_border = "rgba(255, 255, 255, 0.12)"
        vault_entry_text = "#e0e0e0"
        vault_entry_placeholder = "#8f8f8f"
        vault_entry_focus = "rgba(255, 255, 255, 0.18)"

        # Loading overlay
        loading_background = "rgba(0, 0, 0, 0.0)"
        loading_rain_primary = "#e6e6e6"
        loading_rain_secondary = "#bdbdbd"
        loading_ascii = "#f0f0f0"

        # Status bar (GTK)
        status_background = "rgba(12, 12, 12, 0.95)"
        status_border = "rgba(255, 255, 255, 0.06)"
        status_text = "#cfcfcf"
        status_success = "#d0d0d0"
        status_error = "#ff9d9d"

        # Exported HTML base colors
        export_body_background = "#0a0a0a"
        export_body_text = "#d0d0d0"
        export_title = "#e6e6e6"
        export_h1 = "#dedede"
        export_h2 = "#d9d9d9"
        export_h3 = "#d4d4d4"
        export_h4 = "#d0d0d0"
        export_h5 = "#cccccc"
        export_h6 = "#c8c8c8"
        export_body = "#d0d0d0"
        export_toc = "#bfbfbf"
        export_latex = "#d0d0d0"
        export_toggle_bg = "rgba(18, 18, 18, 0.9)"
        export_toggle_text = "#d0d0d0"
        export_toggle_border = "rgba(255, 255, 255, 0.12)"
        export_toggle_active_bg = "#e6e6e6"
        export_toggle_active_text = "#0a0a0a"

        # WebKit HTML text colors
        webkit_three_text = "#ddd"
        webkit_latex_text = "#d0d0d0"
        webkit_map_error_background = "rgba(24, 24, 24, 0.85)"
        webkit_map_error_text = "#d0d0d0"
        webkit_background_rgba = (0.0, 0.0, 0.0, 0.0)

        # Three.js default material and lights
        three_material = 0xAAAAAA
        three_light = 0xFFFFFF
        three_clear = 0x000000

        # Python render defaults
        py_render_text = "#d0d0d0"
        py_render_replacement = "#d0d0d0"
        py_render_replacement_rgb = "rgb(208,208,208)"
        py_render_fallback_fill = "#ffffff"

        # Map block template defaults
        map_marker = "#d0d0d0"
        map_tile_url = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        map_tile_attr = "&copy; OpenStreetMap contributors &copy; CARTO"

    class light:
        """Light-mode palette (placeholder defaults)."""

        # Base GTK text and heading colors (style.css block text)
        block_text = "#2a2a2a"
        block_title = "#111111"
        block_h1 = "#1a1a1a"
        block_h2 = "#202020"
        block_h3 = "#242424"
        block_h4 = "#2a2a2a"
        block_h5 = "#303030"
        block_h6 = "#363636"
        block_toc = "#3a3a3a"
        app_background = "rgba(255, 255, 255, 0.5)"

        # Inline image label text in GTK
        block_image_label = "#2b2b2b"

        # Selection highlight for the active block (GTK)
        block_selected_shadow = "rgba(0, 0, 0, 0.12)"
        block_selected_background = "rgba(240, 240, 240, 0.9)"

        # Help overlay panel (GTK)
        help_panel_background = "rgba(248, 248, 248, 0.95)"
        help_panel_border = "rgba(0, 0, 0, 0.08)"
        help_title = "#111111"
        help_body = "#2b2b2b"

        # TOC drill overlay (GTK)
        toc_panel_background = "rgba(250, 250, 250, 0.96)"
        toc_panel_border = "rgba(0, 0, 0, 0.08)"
        toc_panel_shadow = "rgba(0, 0, 0, 0.12)"
        toc_title = "#111111"
        toc_hint = "#666666"
        toc_row_selected_background = "rgba(230, 230, 230, 0.9)"
        toc_row_selected_border = "rgba(0, 0, 0, 0.06)"
        toc_row_label = "#2a2a2a"
        toc_empty = "#666666"

        # Vault overlay (GTK)
        vault_panel_background = "rgba(250, 250, 250, 0.96)"
        vault_panel_border = "rgba(0, 0, 0, 0.08)"
        vault_panel_shadow = "rgba(0, 0, 0, 0.12)"
        vault_title = "#111111"
        vault_subtitle = "#666666"
        vault_hint = "#666666"
        vault_row_selected_background = "rgba(230, 230, 230, 0.9)"
        vault_row_selected_border = "rgba(0, 0, 0, 0.06)"
        vault_row_label = "#2a2a2a"
        vault_empty = "#666666"
        vault_entry_background = "rgba(255, 255, 255, 0.95)"
        vault_entry_border = "rgba(0, 0, 0, 0.12)"
        vault_entry_text = "#1f1f1f"
        vault_entry_placeholder = "#777777"
        vault_entry_focus = "rgba(0, 0, 0, 0.2)"

        # Loading overlay
        loading_background = "rgba(255, 255, 255, 0.0)"
        loading_rain_primary = "#2b2b2b"
        loading_rain_secondary = "#6b6b6b"
        loading_ascii = "#1f1f1f"

        # Status bar (GTK)
        status_background = "rgba(245, 245, 245, 0.96)"
        status_border = "rgba(0, 0, 0, 0.06)"
        status_text = "#2b2b2b"
        status_success = "#1f7a1f"
        status_error = "#b11a1a"

        # Exported HTML base colors
        export_body_background = "#ffffff"
        export_body_text = "#1f1f1f"
        export_title = "#111111"
        export_h1 = "#1a1a1a"
        export_h2 = "#202020"
        export_h3 = "#242424"
        export_h4 = "#2a2a2a"
        export_h5 = "#303030"
        export_h6 = "#363636"
        export_body = "#1f1f1f"
        export_toc = "#3a3a3a"
        export_latex = "#1f1f1f"
        export_toggle_bg = "rgba(250, 250, 250, 0.9)"
        export_toggle_text = "#1f1f1f"
        export_toggle_border = "rgba(0, 0, 0, 0.12)"
        export_toggle_active_bg = "#111111"
        export_toggle_active_text = "#ffffff"

        # WebKit HTML text colors
        webkit_three_text = "#222"
        webkit_latex_text = "#1f1f1f"
        webkit_map_error_background = "rgba(235, 235, 235, 0.9)"
        webkit_map_error_text = "#1f1f1f"
        webkit_background_rgba = (0.0, 0.0, 0.0, 0.0)

        # Three.js default material and lights
        three_material = 0x444444
        three_light = 0xFFFFFF
        three_clear = 0xFFFFFF

        # Python render defaults
        py_render_text = "#1f1f1f"
        py_render_replacement = "#1f1f1f"
        py_render_replacement_rgb = "rgb(31,31,31)"
        py_render_fallback_fill = "#000000"

        # Map block template defaults
        map_marker = "#0b0b0b"
        map_tile_url = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        map_tile_attr = "&copy; OpenStreetMap contributors &copy; CARTO"


class font:
    """Font size tokens for GTK and export HTML."""

    # GTK block text sizes (style.css)
    block_text = "11px"
    block_title = "22px"
    block_h1 = "18px"
    block_h2 = "15px"
    block_h3 = "13px"
    block_h4 = "12px"
    block_h5 = "11px"
    block_h6 = "10px"
    block_toc = "11px"

    # GTK help/TOC/status sizes
    help_title = "16px"
    help_body = "12px"
    toc_title = "18px"
    toc_hint = "11px"
    toc_row = "12px"
    toc_empty = "12px"
    vault_title = "18px"
    vault_subtitle = "11px"
    vault_hint = "11px"
    vault_row = "12px"
    vault_empty = "12px"
    status = "11px"
    loading_ascii = "12px"

    # Export HTML sizes
    export_title = "28px"
    export_h1 = "20px"
    export_h2 = "16px"
    export_h3 = "14px"
    export_h4 = "13px"
    export_h5 = "12px"
    export_h6 = "11px"
    export_body = "13px"
    export_toc = "13px"
    export_latex = "20px"


def colors_for(mode: str) -> type:
    return colors.dark if mode == "dark" else colors.light
