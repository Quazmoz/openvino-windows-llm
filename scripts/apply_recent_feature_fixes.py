"""Apply focused fixes for the July 2026 feature expansion.

This script is intentionally one-shot. It is run by a temporary GitHub Actions
workflow, which publishes the resulting files and a validation report on a
review branch before the changes are merged to main.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT: list[str] = []
ERRORS: list[str] = []


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str, label: str) -> None:
    text = _read(path)
    if new in text:
        REPORT.append(f"SKIP {label}: already applied")
        return
    count = text.count(old)
    if count != 1:
        message = f"FAIL {label}: expected one exact match in {path}, found {count}"
        REPORT.append(message)
        ERRORS.append(message)
        return
    _write(path, text.replace(old, new, 1))
    REPORT.append(f"PASS {label}")


def regex_once(path: str, pattern: str, replacement: str, label: str) -> None:
    text = _read(path)
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        message = f"FAIL {label}: expected one regex match in {path}, found {count}"
        REPORT.append(message)
        ERRORS.append(message)
        return
    _write(path, updated)
    REPORT.append(f"PASS {label}")


def apply_server_fixes() -> None:
    replace_once(
        "app/server.py",
        "import contextvars\nimport json\n",
        "import contextvars\nimport hashlib\nimport json\n",
        "server imports hashlib",
    )
    replace_once(
        "app/server.py",
        "    stop: list[str] | None = None,\n"
        "    seed: int | None = None,\n"
        "    lora_path: str | None = None,\n",
        "    stop: list[str] | None = None,\n"
        "    seed: int | None = None,\n"
        "    response_format: dict | None = None,\n"
        "    lora_path: str | None = None,\n",
        "generation helper accepts response_format",
    )
    replace_once(
        "app/server.py",
        "        stop=stop or None,\n"
        "        seed=seed,\n"
        "        lora_path=lora_path,\n",
        "        stop=stop or None,\n"
        "        seed=seed,\n"
        "        response_format=response_format,\n"
        "        lora_path=lora_path,\n",
        "generation helper stores response_format",
    )
    replace_once(
        "app/server.py",
        "    for k in valid_keys:\n"
        "        obfuscated = k[:5] + \"...\" if len(k) > 7 else k[:2] + \"...\"\n"
        "        key_stats[k] = {\n"
        "            \"key_name\": obfuscated,\n",
        "    for k in valid_keys:\n"
        "        prefix = k[:5] if len(k) > 7 else k[:2]\n"
        "        fingerprint = hashlib.sha256(k.encode(\"utf-8\")).hexdigest()[:8]\n"
        "        key_stats[k] = {\n"
        "            \"key_name\": f\"{prefix}...{fingerprint}\",\n",
        "API-key stats use distinguishable fingerprints",
    )
    replace_once(
        "app/server.py",
        "        task = manager.schedule_load(req.model, device, draft_model=req.draft_model)\n"
        "        entry = manager.catalog_entry(req.model)\n",
        "        try:\n"
        "            task = manager.schedule_load(req.model, device, draft_model=req.draft_model)\n"
        "        except ValueError as exc:\n"
        "            raise HTTPException(status_code=400, detail=str(exc)) from exc\n"
        "        entry = manager.catalog_entry(req.model)\n",
        "draft validation errors become HTTP 400",
    )
    replace_once(
        "app/server.py",
        "            stop=chat_format.normalize_stop(request.stop),\n"
        "            seed=request.seed,\n"
        "            lora_path=request.lora_path,\n",
        "            stop=chat_format.normalize_stop(request.stop),\n"
        "            seed=request.seed,\n"
        "            response_format=request.response_format,\n"
        "            lora_path=request.lora_path,\n",
        "chat completions forward response_format",
    )
    replace_once(
        "app/server.py",
        "        start = time.perf_counter()\n"
        "        result = await manager.generate(engine, prompt, params)\n"
        "        manager.record_request(\n"
        "            engine.model_id, prompt_tokens, result.completion_tokens, time.perf_counter() - start\n"
        "        )\n"
        "        return ResponseObject(\n",
        "        start = time.perf_counter()\n"
        "        result = await manager.generate(engine, prompt, params)\n"
        "        latency = time.perf_counter() - start\n"
        "        manager.record_request(engine.model_id, prompt_tokens, result.completion_tokens, latency)\n"
        "        record_key_metrics(prompt_tokens, result.completion_tokens, latency)\n"
        "        return ResponseObject(\n",
        "non-stream Responses API records per-key metrics",
    )


def apply_request_model_fixes() -> None:
    replace_once(
        "app/openai_api.py",
        "    response_format: Any | None = None  # response format constraint (JSON object or JSON Schema)\n"
        "    lora_path: str | None = None  # path to safetensors LoRA weights\n"
        "    lora_alpha: float | None = 1.0  # scaling factor for LoRA weights\n",
        "    response_format: dict[str, Any] | None = None  # JSON object or JSON Schema constraint\n"
        "    lora_path: str | None = None  # path to safetensors LoRA weights\n"
        "    lora_alpha: float | None = Field(default=1.0, gt=0.0)\n",
        "validate chat structured-output and LoRA inputs",
    )
    replace_once(
        "app/openai_api.py",
        "    lora_path: str | None = None\n    lora_alpha: float | None = 1.0\n",
        "    lora_path: str | None = None\n"
        "    lora_alpha: float | None = Field(default=1.0, gt=0.0)\n",
        "validate Responses API LoRA alpha",
    )
    replace_once(
        "app/openai_api.py",
        "    weight_format: str | None = None\n"
        "    group_size: int | None = None\n"
        "    ratio: float | None = None\n",
        "    weight_format: str | None = Field(default=None, pattern=r\"^(int4|int8|fp16)$\")\n"
        "    group_size: int | None = Field(default=None, ge=-1)\n"
        "    ratio: float | None = Field(default=None, ge=0.0, le=1.0)\n",
        "validate model conversion options",
    )
    replace_once(
        "app/openai_api.py",
        "    group_size: int | None = None\n"
        "    ratio: float | None = None\n"
        "    sym: bool | None = None\n"
        "    recommended_device: str = Field(default=\"CPU\", min_length=1, max_length=64)\n",
        "    group_size: int | None = Field(default=None, ge=-1)\n"
        "    ratio: float | None = Field(default=None, ge=0.0, le=1.0)\n"
        "    sym: bool | None = None\n"
        "    recommended_device: str = Field(default=\"CPU\", min_length=1, max_length=64)\n",
        "validate custom download quantization options",
    )
    replace_once(
        "app/openai_api.py",
        "    description: str | None = None\n    load_after: bool = True\n",
        "    description: str | None = None\n"
        "    load_after: bool = True\n\n"
        "    @field_validator(\"recommended_device\")\n"
        "    @classmethod\n"
        "    def validate_recommended_device(cls, value: str) -> str:\n"
        "        try:\n"
        "            return device_check.validate_device_expression(value)\n"
        "        except device_check.DeviceValidationError as exc:\n"
        "            raise ValueError(str(exc)) from exc\n",
        "validate custom download device",
    )


def apply_registry_and_manager_fixes() -> None:
    replace_once(
        "app/model_registry.py",
        "def is_downloaded(cfg: ModelConfig, base_dir: Path) -> bool:\n"
        "    \"\"\"True if a converted OpenVINO IR directory exists for this model.\"\"\"\n"
        "    model_dir = cfg.abs_path(base_dir)\n"
        "    if not model_dir.is_dir():\n"
        "        return False\n"
        "    return any((model_dir / marker).exists() for marker in _IR_MARKERS)\n",
        "def is_openvino_model_dir(model_dir: Path) -> bool:\n"
        "    \"\"\"Return whether *model_dir* contains a converted OpenVINO IR model.\"\"\"\n"
        "    model_dir = Path(model_dir)\n"
        "    return model_dir.is_dir() and any(\n"
        "        (model_dir / marker).exists() for marker in _IR_MARKERS\n"
        "    )\n\n\n"
        "def is_downloaded(cfg: ModelConfig, base_dir: Path) -> bool:\n"
        "    \"\"\"True if a converted OpenVINO IR directory exists for this model.\"\"\"\n"
        "    return is_openvino_model_dir(cfg.abs_path(base_dir))\n",
        "centralize converted OpenVINO directory validation",
    )
    replace_once(
        "app/model_manager.py",
        "    def _build_engine(\n"
        "        self, model_id: str, device: str, draft_model_path: str | None = None\n"
        "    ) -> BaseEngine:\n",
        "    def _resolve_draft_model_path(\n"
        "        self, model_id: str, draft_model: str | None\n"
        "    ) -> str | None:\n"
        "        if not draft_model:\n"
        "            return None\n"
        "        if draft_model == model_id:\n"
        "            raise ValueError(\"Draft model must differ from the target model.\")\n\n"
        "        draft_cfg = self.catalog.get(draft_model)\n"
        "        if draft_cfg is not None:\n"
        "            if \"embedding\" in draft_cfg.backend.lower():\n"
        "                raise ValueError(\n"
        "                    f\"Draft model '{draft_model}' is an embedding model; \"\n"
        "                    \"speculative decoding requires a text-generation model.\"\n"
        "                )\n"
        "            if not self.force_mock and not registry.is_downloaded(draft_cfg, BASE_DIR):\n"
        "                raise ValueError(f\"Draft model '{draft_model}' is not converted locally.\")\n"
        "            return str(draft_cfg.abs_path(BASE_DIR))\n\n"
        "        path = Path(draft_model).expanduser()\n"
        "        path = path.resolve() if path.is_absolute() else (BASE_DIR / path).resolve()\n"
        "        if not path.is_dir():\n"
        "            raise ValueError(\n"
        "                f\"Draft model path does not exist or is not a directory: {path}\"\n"
        "            )\n"
        "        if not self.force_mock and not registry.is_openvino_model_dir(path):\n"
        "            raise ValueError(f\"Draft model path is not a converted OpenVINO model: {path}\")\n"
        "        return str(path)\n\n"
        "    def _build_engine(\n"
        "        self, model_id: str, device: str, draft_model_path: str | None = None\n"
        "    ) -> BaseEngine:\n",
        "add draft model validation",
    )
    replace_once(
        "app/model_manager.py",
        "    async def _load_task(\n"
        "        self, model_id: str, device: str, draft_model: str | None = None\n"
        "    ) -> None:\n",
        "    async def _load_task(\n"
        "        self, model_id: str, device: str, draft_model_path: str | None = None\n"
        "    ) -> None:\n",
        "load task accepts validated draft path",
    )
    replace_once(
        "app/model_manager.py",
        "                      draft_model_path = None\n"
        "                      if draft_model:\n"
        "                          if draft_model in self.catalog:\n"
        "                              draft_model_path = str(self.catalog[draft_model].abs_path(BASE_DIR))\n"
        "                          else:\n"
        "                              draft_model_path = draft_model\n\n"
        "                      loop = asyncio.get_running_loop()\n",
        "                      loop = asyncio.get_running_loop()\n",
        "remove unvalidated draft path resolution",
    )
    replace_once(
        "app/model_manager.py",
        "        device = device_check.normalize_device(device or self.settings.device)\n"
        "        cfg = self.catalog[model_id]\n",
        "        draft_model_path = self._resolve_draft_model_path(model_id, draft_model)\n"
        "        device = device_check.normalize_device(device or self.settings.device)\n"
        "        cfg = self.catalog[model_id]\n",
        "validate draft before queueing load",
    )
    replace_once(
        "app/model_manager.py",
        "        task = asyncio.create_task(\n"
        "            self._load_task(model_id, device, draft_model=draft_model)\n"
        "        )\n",
        "        task = asyncio.create_task(\n"
        "            self._load_task(model_id, device, draft_model_path=draft_model_path)\n"
        "        )\n",
        "pass validated draft path to load task",
    )
    replace_once(
        "app/model_manager.py",
        "            backend=\"openvino-genai\",\n"
        "            model_path=f\"models/openvino/{req.model_id}\",\n",
        "            backend=getattr(req, \"backend\", \"openvino-genai\"),\n"
        "            model_path=f\"models/openvino/{req.model_id}\",\n",
        "preserve custom model backend",
    )


def apply_converter_and_engine_fixes() -> None:
    replace_once(
        "runtime/model_converter.py",
        "def _resolve_from_catalog(model_id: str) -> tuple[str, Path, str]:\n"
        "    \"\"\"Look up source model, output dir, and weight format from models.json.\"\"\"\n",
        "def _resolve_from_catalog(model_id: str) -> tuple[str, Path, str, str | None]:\n"
        "    \"\"\"Look up source model, output dir, weight format, and Optimum task.\"\"\"\n",
        "converter catalog lookup returns task",
    )
    replace_once(
        "runtime/model_converter.py",
        "    return cfg.source_model, cfg.abs_path(BASE_DIR), cfg.weight_format\n",
        "    task = \"feature-extraction\" if \"embedding\" in cfg.backend.lower() else None\n"
        "    return cfg.source_model, cfg.abs_path(BASE_DIR), cfg.weight_format, task\n",
        "converter infers embedding task",
    )
    replace_once(
        "runtime/model_converter.py",
        "    args = parser.parse_args(argv)\n\n"
        "    if args.id:\n"
        "        source_model, output_dir, weight_format = _resolve_from_catalog(args.id)\n"
        "        weight_format = args.weight_format or weight_format\n",
        "    args = parser.parse_args(argv)\n\n"
        "    if args.ratio is not None and not 0.0 <= args.ratio <= 1.0:\n"
        "        parser.error(\"--ratio must be between 0.0 and 1.0\")\n"
        "    if args.group_size is not None and args.group_size != -1 and args.group_size <= 0:\n"
        "        parser.error(\"--group-size must be -1 or a positive integer\")\n\n"
        "    task = args.task\n"
        "    if args.id:\n"
        "        source_model, output_dir, weight_format, catalog_task = _resolve_from_catalog(\n"
        "            args.id\n"
        "        )\n"
        "        weight_format = args.weight_format or weight_format\n"
        "        task = task or catalog_task\n",
        "converter validates quantization and uses catalog task",
    )
    replace_once(
        "runtime/model_converter.py",
        "            task=args.task,\n",
        "            task=task,\n",
        "converter forwards resolved task",
    )
    replace_once(
        "runtime/openvino_engine.py",
        "import contextlib\nimport logging\n",
        "import contextlib\nimport hashlib\nimport logging\n",
        "engine imports hashlib",
    )
    replace_once(
        "runtime/openvino_engine.py",
        "from pathlib import Path\n",
        "from pathlib import Path\nfrom typing import Any\n",
        "engine imports Any",
    )
    replace_once(
        "runtime/openvino_engine.py",
        "            # Deterministic generation using a seed derived from the text hash\n"
        "            rng = random.Random(hash(text))\n",
        "            # Use a stable digest rather than Python's process-randomized hash().\n"
        "            seed = int.from_bytes(\n"
        "                hashlib.sha256(text.encode(\"utf-8\")).digest()[:8], \"big\"\n"
        "            )\n"
        "            rng = random.Random(seed)\n",
        "mock embeddings are reproducible across processes",
    )
    replace_once(
        "runtime/openvino_engine.py",
        "            draft_model_fn = getattr(ov_genai, \"draft_model\", None)\n"
        "            if draft_model_fn is not None:\n"
        "                draft_device = self.device\n"
        "                if self.device == \"NPU\":\n"
        "                    draft_device = \"CPU\"\n"
        "                try:\n"
        "                    draft_obj = draft_model_fn(str(draft_model_path), draft_device)\n"
        "                except Exception as exc:\n"
        "                    logger.error(\"Failed to load draft model: %s\", exc)\n"
        "            else:\n"
        "                logger.warning(\n"
        "                    \"openvino_genai.draft_model is not available in this OpenVINO version.\"\n"
        "                )\n",
        "            draft_model_fn = getattr(ov_genai, \"draft_model\", None)\n"
        "            if draft_model_fn is None:\n"
        "                raise RuntimeError(\n"
        "                    \"This OpenVINO GenAI version does not support speculative decoding.\"\n"
        "                )\n"
        "            try:\n"
        "                draft_obj = draft_model_fn(str(draft_model_path), self.device)\n"
        "            except Exception as exc:\n"
        "                raise RuntimeError(\n"
        "                    f\"Failed to load draft model '{draft_model_path}': {exc}\"\n"
        "                ) from exc\n",
        "requested speculative decoding fails loudly and stays on requested device",
    )
    replace_once(
        "runtime/openvino_engine.py",
        "                        so_cfg = StructuredOutputConfig()\n"
        "                        so_cfg.json_schema = json.dumps(schema_data)\n",
        "                        so_cfg = StructuredOutputConfig(\n"
        "                            json_schema=json.dumps(schema_data)\n"
        "                        )\n",
        "construct JSON-schema output config canonically",
    )
    replace_once(
        "runtime/openvino_engine.py",
        "                    so_cfg = StructuredOutputConfig()\n"
        "                    so_cfg.json_schema = json.dumps({\"type\": \"object\"})\n",
        "                    so_cfg = StructuredOutputConfig(\n"
        "                        json_schema=json.dumps({\"type\": \"object\"})\n"
        "                    )\n",
        "construct JSON-object output config canonically",
    )
    replace_once(
        "runtime/openvino_engine.py",
        "        if Adapter is not None and AdapterConfig is not None:\n"
        "            try:\n"
        "                adapters_config = AdapterConfig()\n"
        "                adapters_config.add(\n"
        "                    Adapter(str(params.lora_path)), alpha=float(params.lora_alpha or 1.0)\n"
        "                )\n"
        "                return adapters_config\n"
        "            except Exception as exc:\n"
        "                logger.error(\n"
        "                    \"Failed to construct AdapterConfig for %s: %s\", params.lora_path, exc\n"
        "                )\n"
        "        return None\n",
        "        if Adapter is None or AdapterConfig is None:\n"
        "            raise RuntimeError(\n"
        "                \"This OpenVINO GenAI version does not support dynamic LoRA adapters.\"\n"
        "            )\n"
        "        try:\n"
        "            adapters_config = AdapterConfig()\n"
        "            adapters_config.add(\n"
        "                Adapter(str(params.lora_path)), alpha=float(params.lora_alpha or 1.0)\n"
        "            )\n"
        "            return adapters_config\n"
        "        except Exception as exc:\n"
        "            raise RuntimeError(\n"
        "                f\"Failed to construct LoRA adapter config for '{params.lora_path}': {exc}\"\n"
        "            ) from exc\n",
        "requested LoRA failures are not silently ignored",
    )


def apply_ui_and_test_fixes() -> None:
    replace_once(
        "web/index.html",
        "                max_output_tokens: parseInt(customMaxOutputTokens.value, 10),\n"
        "                load_after: true\n",
        "                max_output_tokens: parseInt(customMaxOutputTokens.value, 10),\n"
        "                description: customDescription.value.trim() || null,\n"
        "                load_after: true\n",
        "custom model UI preserves description",
    )
    replace_once(
        "tests/test_server_mock.py",
        '                "draft_model": "bge-small-en-v1.5",\n',
        '                "draft_model": "smollm2-135m-fp16",\n',
        "existing speculative test uses a text-generation draft",
    )
    replace_once(
        "tests/test_server_mock.py",
        '        assert "bge-small-en-v1.5" in args[2]  # draft path contains model name\n',
        '        assert "smollm2-135m-fp16" in args[2]  # draft path contains model name\n',
        "existing speculative assertion uses valid draft",
    )
    replace_once(
        "tests/test_server_mock.py",
        '        assert "ke..." in names\n',
        '        assert len(set(names)) == 2\n'
        '        assert all(name.startswith("ke...") for name in names)\n',
        "existing key stats test expects distinct labels",
    )
    regression_test = '''"""Regression coverage for the July 2026 OpenVINO feature expansion."""

import hashlib
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import BASE_DIR, Settings
from app.server import create_app
from runtime.openvino_engine import GenResult

MODEL_ID = "tinyllama-1.1b-chat-fp16"


def _client(tmp_path: Path, *, api_key: str | None = None) -> TestClient:
    models_file = tmp_path / "models.json"
    models_file.write_text(
        (BASE_DIR / "models.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    settings = Settings(
        host="127.0.0.1",
        port=8000,
        device="CPU",
        models_file=models_file,
        models_dir=BASE_DIR / "models" / "openvino",
        default_model=None,
        api_key=api_key,
        force_mock=True,
    )
    return TestClient(create_app(settings))


def _load(
    client: TestClient, model_id: str = MODEL_ID, headers: dict[str, str] | None = None
) -> None:
    response = client.post(
        "/v1/models/load", json={"model": model_id}, headers=headers or {}
    )
    assert response.status_code == 200, response.text
    deadline = time.time() + 5
    while time.time() < deadline:
        status = client.get("/v1/system/status", headers=headers or {}).json()
        if model_id in status["models"]["loaded"]:
            return
        time.sleep(0.02)
    raise AssertionError(f"{model_id} did not load")


def test_structured_output_is_forwarded_to_generation(tmp_path: Path) -> None:
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "person",
            "schema": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    }
    with _client(tmp_path) as client:
        _load(client)
        manager = client.app.state.manager
        captured = {}

        async def fake_generate(engine, prompt, params):
            captured["response_format"] = params.response_format
            return GenResult(text='{"name":"Ada"}', completion_tokens=4)

        manager.generate = fake_generate
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": MODEL_ID,
                "messages": [{"role": "user", "content": "Return a person"}],
                "response_format": response_format,
            },
        )
        assert response.status_code == 200, response.text
        assert captured["response_format"] == response_format


def test_embedding_model_cannot_be_used_as_speculative_draft(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.post(
            "/v1/models/load",
            json={"model": MODEL_ID, "draft_model": "bge-small-en-v1.5"},
        )
        assert response.status_code == 400
        assert "embedding model" in response.json()["detail"]
        assert MODEL_ID not in client.app.state.manager.load_tasks


def test_custom_embedding_registration_preserves_backend(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        manager = client.app.state.manager

        def fake_schedule_convert(model_id, device=None, **kwargs):
            manager._set_status(model_id, "queued_convert")
            return object()

        manager.schedule_convert = fake_schedule_convert
        response = client.post(
            "/v1/models/download-custom",
            json={
                "model_id": "custom-embedding-regression",
                "name": "Custom Embedding Regression",
                "source_model": "BAAI/bge-small-en-v1.5",
                "backend": "openvino-embeddings",
                "weight_format": "fp16",
                "recommended_device": "CPU",
                "max_context_len": 512,
                "max_output_tokens": 0,
                "load_after": False,
            },
        )
        assert response.status_code == 200, response.text
        config = manager.catalog["custom-embedding-regression"]
        assert config.backend == "openvino-embeddings"
        assert response.json()["model"]["backend"] == "openvino-embeddings"


def test_nonstream_responses_are_attributed_to_the_calling_key(tmp_path: Path) -> None:
    beta_headers = {"Authorization": "Bearer beta-key"}
    alpha_headers = {"Authorization": "Bearer alpha-key"}
    with _client(tmp_path, api_key="alpha-key,beta-key") as client:
        _load(client, headers=beta_headers)
        response = client.post(
            "/v1/responses",
            headers=beta_headers,
            json={"model": MODEL_ID, "input": "hello", "stream": False},
        )
        assert response.status_code == 200, response.text

        stats_response = client.get("/v1/keys/stats", headers=alpha_headers)
        assert stats_response.status_code == 200
        stats = stats_response.json()
        fingerprint = hashlib.sha256(b"beta-key").hexdigest()[:8]
        beta_stats = next(
            item for item in stats if item["key_name"].endswith(fingerprint)
        )
        assert beta_stats["requests"] == 1
        assert beta_stats["prompt_tokens"] > 0
        assert beta_stats["completion_tokens"] > 0
'''
    _write("tests/test_recent_feature_regressions.py", regression_test)
    REPORT.append("PASS add recent feature regression tests")


def main() -> int:
    apply_server_fixes()
    apply_request_model_fixes()
    apply_registry_and_manager_fixes()
    apply_converter_and_engine_fixes()
    apply_ui_and_test_fixes()
    report = "\n".join(REPORT) + "\n"
    if ERRORS:
        report += "\nReplacement errors:\n" + "\n".join(ERRORS) + "\n"
    (ROOT / "repair-apply-report.txt").write_text(report, encoding="utf-8")
    print(report, end="")
    return 1 if ERRORS else 0


if __name__ == "__main__":
    raise SystemExit(main())
