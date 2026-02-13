"""Python rendering runner."""

from __future__ import annotations

import base64
import hashlib
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RenderResult:
    rendered_data: str | None
    rendered_hash: str | None
    error: str | None


def render_python_image(
    source: str, python_path: str, render_format: str = "png"
) -> RenderResult:
    if not python_path:
        return RenderResult(None, None, "Python path not configured")

    render_format = (render_format or "png").lower()
    if render_format not in ("png", "svg"):
        render_format = "png"

    render_hash = _hash_render(source, python_path, render_format)

    with tempfile.TemporaryDirectory(prefix="gtkv-pyimage-") as temp_dir:
        temp_root = Path(temp_dir)
        output_path = temp_root / f"render.{render_format}"
        source_path = temp_root / "source.py"
        runner_path = temp_root / "runner.py"

        source_path.write_text(source, encoding="utf-8")
        runner_path.write_text(
            _build_runner_script(source_path, output_path, render_format),
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
            if render_format == "svg":
                rendered_text = output_path.read_text(encoding="utf-8")
                return RenderResult(rendered_text, render_hash, None)
            rendered_bytes = output_path.read_bytes()
        except OSError as exc:
            return RenderResult(None, render_hash, f"Failed to read output: {exc}")

        encoded = base64.b64encode(rendered_bytes).decode("utf-8")
        return RenderResult(encoded, render_hash, None)


def _hash_render(source: str, python_path: str, render_format: str) -> str:
    digest = hashlib.sha256()
    digest.update(python_path.encode("utf-8"))
    digest.update(render_format.encode("utf-8"))
    digest.update(source.encode("utf-8"))
    return digest.hexdigest()


def _build_runner_script(
    source_path: Path, output_path: Path, render_format: str
) -> str:
    return (
        "from types import SimpleNamespace\n"
        f"__gtkv__ = SimpleNamespace(renderer={output_path.as_posix()!r}, format={render_format!r})\n"
        f"_source = {source_path.as_posix()!r}\n"
        "with open(_source, 'r', encoding='utf-8') as _file:\n"
        "    _code = _file.read()\n"
        "_globals = {'__gtkv__': __gtkv__}\n"
        "exec(compile(_code, _source, 'exec'), _globals)\n"
    )
