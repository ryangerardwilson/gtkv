"""Python rendering runner."""

from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import config
from design_constants import colors_for


@dataclass
class RenderResult:
    rendered_data: str | None
    rendered_hash: str | None
    error: str | None


def render_python_image(
    source: str,
    python_path: str,
    render_format: str = "png",
    ui_mode: str | None = None,
) -> RenderResult:
    if not python_path:
        return RenderResult(None, None, "Python path not configured")

    render_format = (render_format or "svg").lower()
    if render_format != "svg":
        return RenderResult(None, None, "Python render format must be svg")

    render_hash = _hash_render(source, python_path, render_format)

    with tempfile.TemporaryDirectory(prefix="gtkv-pyimage-") as temp_dir:
        temp_root = Path(temp_dir)
        output_path = temp_root / f"render.{render_format}"
        source_path = temp_root / "source.py"
        runner_path = temp_root / "runner.py"

        source_path.write_text(source, encoding="utf-8")
        runner_path.write_text(
            _build_runner_script(
                source_path, output_path, render_format, ui_mode=ui_mode
            ),
            encoding="utf-8",
        )

        result = subprocess.run(
            [python_path, runner_path.as_posix()],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip() or "Render failed"
            return RenderResult(None, render_hash, error)

        if not output_path.exists():
            return RenderResult(None, render_hash, "Renderer did not write output")

        try:
            rendered_text = output_path.read_text(encoding="utf-8")
        except OSError as exc:
            return RenderResult(None, render_hash, f"Failed to read output: {exc}")

        rendered_text = _replace_black_with_white_svg(rendered_text, ui_mode)
        return RenderResult(rendered_text, render_hash, None)


def _hash_render(source: str, python_path: str, render_format: str) -> str:
    digest = hashlib.sha256()
    digest.update(b"gtkv-pyimage-v2")
    digest.update(python_path.encode("utf-8"))
    digest.update(render_format.encode("utf-8"))
    digest.update(source.encode("utf-8"))
    return digest.hexdigest()


def _build_runner_script(
    source_path: Path,
    output_path: Path,
    render_format: str,
    ui_mode: str | None = None,
) -> str:
    palette = colors_for(ui_mode or config.get_ui_mode() or "dark")
    return (
        "from types import SimpleNamespace\n"
        "import matplotlib as _mpl\n"
        "_mpl.rcParams.update({\n"
        f"    'text.color': '{palette.py_render_text}',\n"
        f"    'axes.labelcolor': '{palette.py_render_text}',\n"
        f"    'xtick.labelcolor': '{palette.py_render_text}',\n"
        f"    'xtick.color': '{palette.py_render_text}',\n"
        f"    'ytick.labelcolor': '{palette.py_render_text}',\n"
        f"    'ytick.color': '{palette.py_render_text}',\n"
        f"    'axes.edgecolor': '{palette.py_render_text}',\n"
        f"    'axes.titlecolor': '{palette.py_render_text}',\n"
        "    'axes.facecolor': 'none',\n"
        "    'figure.facecolor': 'none',\n"
        "    'savefig.transparent': True,\n"
        "})\n"
        f"__gtkv__ = SimpleNamespace(renderer={output_path.as_posix()!r}, format={render_format!r})\n"
        f"_source = {source_path.as_posix()!r}\n"
        "with open(_source, 'r', encoding='utf-8') as _file:\n"
        "    _code = _file.read()\n"
        "_globals = {'__gtkv__': __gtkv__}\n"
        "exec(compile(_code, _source, 'exec'), _globals)\n"
    )


def _replace_black_with_white_svg(svg_text: str, ui_mode: str | None = None) -> str:
    palette = colors_for(ui_mode or config.get_ui_mode() or "dark")
    replacement_rgb = palette.py_render_replacement_rgb
    updated = svg_text
    replacements = {
        "#000000": palette.py_render_replacement,
        "#000": palette.py_render_replacement,
        "rgb(0,0,0)": replacement_rgb,
        "rgb(0, 0, 0)": replacement_rgb,
        "black": palette.py_render_replacement,
    }
    for before, after in replacements.items():
        updated = updated.replace(before, after)
        updated = updated.replace(before.upper(), after)

    patterns = [
        r"(fill\s*=\s*\")(#0{3}|#0{6}|#0{8}|black)",
        r"(stroke\s*=\s*\")(#0{3}|#0{6}|#0{8}|black)",
        r"(fill\s*:\s*)(#0{3}|#0{6}|#0{8}|black)",
        r"(stroke\s*:\s*)(#0{3}|#0{6}|#0{8}|black)",
        r"(fill\s*=\s*\")(rgb\(0\s*,\s*0\s*,\s*0\)|rgb\(0%\s*,\s*0%\s*,\s*0%\)|rgba\(0\s*,\s*0\s*,\s*0\s*,\s*1\))",
        r"(stroke\s*=\s*\")(rgb\(0\s*,\s*0\s*,\s*0\)|rgb\(0%\s*,\s*0%\s*,\s*0%\)|rgba\(0\s*,\s*0\s*,\s*0\s*,\s*1\))",
        r"(fill\s*:\s*)(rgb\(0\s*,\s*0\s*,\s*0\)|rgb\(0%\s*,\s*0%\s*,\s*0%\)|rgba\(0\s*,\s*0\s*,\s*0\s*,\s*1\))",
        r"(stroke\s*:\s*)(rgb\(0\s*,\s*0\s*,\s*0\)|rgb\(0%\s*,\s*0%\s*,\s*0%\)|rgba\(0\s*,\s*0\s*,\s*0\s*,\s*1\))",
    ]
    for pattern in patterns:
        updated = re.sub(
            pattern,
            rf"\1{palette.py_render_replacement}",
            updated,
            flags=re.IGNORECASE,
        )

    def _force_text_fill(match: re.Match) -> str:
        prefix = match.group(1)
        attrs = match.group(2) or ""
        if "style=" in attrs:
            return f"{prefix}{_append_fill_style(attrs)}"
        return f'{prefix}{attrs} style="fill:{palette.py_render_replacement}"'

    updated = re.sub(
        r"(<g\s+id=\"text_\d+\")([^>]*)",
        _force_text_fill,
        updated,
    )

    return updated


def _append_fill_style(attrs: str) -> str:
    palette = colors_for(config.get_ui_mode() or "dark")
    match = re.search(r"style=\"([^\"]*)\"", attrs)
    if not match:
        return f'{attrs} style="fill:{palette.py_render_fallback_fill}"'
    style = match.group(1)
    if "fill:" in style:
        updated_style = re.sub(
            r"fill\s*:[^;]+", f"fill:{palette.py_render_replacement}", style
        )
    else:
        updated_style = f"{style};fill:{palette.py_render_replacement}"
    return attrs.replace(match.group(0), f'style="{updated_style}"')
