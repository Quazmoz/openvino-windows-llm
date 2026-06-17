"""Helper for exporting Hugging Face models to OpenVINO IR via Optimum Intel.

Conversion is a separate, heavier step than serving and requires the extra
``requirements-convert.txt`` dependencies. This module builds and runs the
``optimum-cli export openvino`` command and can resolve a model by its
``models.json`` id so paths/weights stay consistent with the server.

Usage:
    python -m runtime.model_converter --id tinyllama-1.1b-chat-fp16
    python -m runtime.model_converter --model Qwen/Qwen2.5-1.5B-Instruct \
        --output models/openvino/qwen2.5-1.5b-instruct-fp16 --weight-format fp16
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Ensure the virtual environment's Scripts/bin directory is on PATH so that
# optimum-cli can be found when running within the venv.
_venv_bin = str(Path(sys.executable).parent)
if _venv_bin not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _venv_bin + os.pathsep + os.environ.get("PATH", "")

logger = logging.getLogger("ov-llm.convert")


def build_export_command(
    source_model: str,
    output_dir: str | Path,
    weight_format: str = "int4",
    *,
    trust_remote_code: bool = True,
    task: str | None = None,
) -> list[str]:
    """Construct the ``optimum-cli export openvino`` argument list."""
    cmd = [
        "optimum-cli",
        "export",
        "openvino",
        "--model",
        source_model,
        "--weight-format",
        weight_format,
    ]
    if task:
        cmd += ["--task", task]
    if trust_remote_code:
        cmd.append("--trust-remote-code")
    cmd.append(str(output_dir))
    return cmd


def export_model(
    source_model: str,
    output_dir: str | Path,
    weight_format: str = "int4",
    *,
    trust_remote_code: bool = True,
    task: str | None = None,
) -> Path:
    """Run the export and return the output directory.

    Raises ``RuntimeError`` if ``optimum-cli`` is not installed and
    ``subprocess.CalledProcessError`` if the export itself fails.
    """
    if shutil.which("optimum-cli") is None:
        raise RuntimeError(
            "optimum-cli not found. Install conversion deps: "
            "pip install -r requirements-convert.txt"
        )

    output_dir = Path(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_export_command(
        source_model, output_dir, weight_format, trust_remote_code=trust_remote_code, task=task
    )
    logger.info("Running: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)
    logger.info("Exported %s -> %s", source_model, output_dir)
    return output_dir


def _resolve_from_catalog(model_id: str) -> tuple[str, Path, str]:
    """Look up source model, output dir, and weight format from models.json."""
    from app.config import Settings
    from app.model_registry import load_catalog

    settings = Settings.from_env()
    catalog = load_catalog(settings.models_file)
    cfg = catalog.get(model_id)
    if cfg is None:
        raise SystemExit(
            f"Unknown model id '{model_id}'. Known ids: {', '.join(catalog) or '(none)'}"
        )
    if not cfg.source_model:
        raise SystemExit(f"Model '{model_id}' has no 'source_model' in models.json")
    from app.config import BASE_DIR

    return cfg.source_model, cfg.abs_path(BASE_DIR), cfg.weight_format


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Export a model to OpenVINO IR.")
    parser.add_argument("--id", help="Model id from models.json (resolves source/output/weights)")
    parser.add_argument("--model", help="Hugging Face source model id")
    parser.add_argument("--output", help="Output directory for the OpenVINO IR model")
    parser.add_argument(
        "--weight-format",
        choices=("int4", "int8", "fp16"),
        default=None,
        help="Override output weights. With --id, defaults to the catalog value; otherwise int4.",
    )
    parser.add_argument("--task", default=None, help="Optional optimum task override")
    parser.add_argument("--no-trust-remote-code", action="store_true")
    args = parser.parse_args(argv)

    if args.id:
        source_model, output_dir, weight_format = _resolve_from_catalog(args.id)
        weight_format = args.weight_format or weight_format
    else:
        if not args.model or not args.output:
            parser.error("Provide either --id, or both --model and --output")
        source_model = args.model
        output_dir = Path(args.output)
        weight_format = args.weight_format or "int4"

    try:
        export_model(
            source_model,
            output_dir,
            weight_format,
            trust_remote_code=not args.no_trust_remote_code,
            task=args.task,
        )
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Conversion failed: {exc}", file=sys.stderr)
        return 1
    print(f"Done. Model available at: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
