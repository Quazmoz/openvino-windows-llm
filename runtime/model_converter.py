"""Export Hugging Face models to OpenVINO IR via Optimum Intel.

Conversion is a separate, heavier step than serving and requires the extra
``requirements-convert.txt`` dependencies. Catalog backends select the matching
Optimum task for text generation, embeddings, or vision-language models.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

_venv_bin = str(Path(sys.executable).parent)
if _venv_bin not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _venv_bin + os.pathsep + os.environ.get("PATH", "")

logger = logging.getLogger("ov-llm.convert")


def build_export_command(
    source_model: str,
    output_dir: str | Path,
    weight_format: str = "int4",
    *,
    trust_remote_code: bool = False,
    task: str | None = None,
    group_size: int | None = None,
    ratio: float | None = None,
    sym: bool | None = None,
) -> list[str]:
    """Construct the ``optimum-cli export openvino`` command."""

    command = [
        "optimum-cli",
        "export",
        "openvino",
        "--model",
        source_model,
        "--weight-format",
        weight_format,
    ]
    if task:
        command += ["--task", task]
    if trust_remote_code:
        command.append("--trust-remote-code")
    if weight_format == "int4":
        if group_size is not None:
            command += ["--group-size", str(group_size)]
        if ratio is not None:
            command += ["--ratio", str(ratio)]
        if sym:
            command.append("--sym")
    command.append(str(output_dir))
    return command


def export_model(
    source_model: str,
    output_dir: str | Path,
    weight_format: str = "int4",
    *,
    trust_remote_code: bool = False,
    task: str | None = None,
    group_size: int | None = None,
    ratio: float | None = None,
    sym: bool | None = None,
) -> Path:
    """Run an export and return its output directory."""

    if shutil.which("optimum-cli") is None:
        raise RuntimeError(
            "optimum-cli not found. Install conversion deps: "
            "pip install -r requirements-convert.txt"
        )

    output_dir = Path(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    if trust_remote_code:
        logger.warning(
            "Running with --trust-remote-code: model '%s' may execute arbitrary code from "
            "the Hugging Face repo during conversion. Only use this with models you trust.",
            source_model,
        )
    command = build_export_command(
        source_model,
        output_dir,
        weight_format,
        trust_remote_code=trust_remote_code,
        task=task,
        group_size=group_size,
        ratio=ratio,
        sym=sym,
    )
    logger.info("Running: %s", " ".join(command))
    subprocess.run(command, check=True)
    logger.info("Exported %s -> %s", source_model, output_dir)
    return output_dir


def _resolve_from_catalog(
    model_id: str, *, include_task: bool = False
) -> tuple[str, Path, str] | tuple[str, Path, str, str | None, bool]:
    """Look up catalog conversion settings, optionally including the Optimum task."""

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

    result = (cfg.source_model, cfg.abs_path(BASE_DIR), cfg.weight_format)
    if not include_task:
        return result

    backend = cfg.backend.lower()
    if "embedding" in backend:
        task = "feature-extraction"
    elif "vlm" in backend or "vision" in backend:
        task = "image-text-to-text"
    else:
        task = None
    return (*result, task, cfg.trust_remote_code)


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
    parser.add_argument(
        "--trust-remote-code",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Allow Hugging Face repository code to execute during export. Disabled by "
            "default; with --id, the catalog setting is used when this flag is omitted."
        ),
    )
    parser.add_argument(
        "--group-size", type=int, default=None, help="Quantization group size for INT4"
    )
    parser.add_argument(
        "--ratio", type=float, default=None, help="Quantization ratio for INT4 (0.0 to 1.0)"
    )
    parser.add_argument("--sym", action="store_true", help="Enable symmetric quantization for INT4")
    args = parser.parse_args(argv)

    if args.ratio is not None and not 0.0 <= args.ratio <= 1.0:
        parser.error("--ratio must be between 0.0 and 1.0")
    if args.group_size is not None and args.group_size != -1 and args.group_size <= 0:
        parser.error("--group-size must be -1 or a positive integer")

    task = args.task
    catalog_trust_remote_code = False
    if args.id:
        source_model, output_dir, weight_format, catalog_task, catalog_trust_remote_code = (
            _resolve_from_catalog(args.id, include_task=True)
        )
        weight_format = args.weight_format or weight_format
        task = task or catalog_task
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
            trust_remote_code=(
                args.trust_remote_code
                if args.trust_remote_code is not None
                else catalog_trust_remote_code
            ),
            task=task,
            group_size=args.group_size,
            ratio=args.ratio,
            sym=args.sym,
        )
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Conversion failed: {exc}", file=sys.stderr)
        return 1
    print(f"Done. Model available at: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
