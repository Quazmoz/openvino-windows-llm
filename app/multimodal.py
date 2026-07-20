"""Validated image inputs and request-local transport for vision-language models.

OpenAI APIs represent images as content parts while the server's established engine
abstraction passes a rendered prompt string. This module bridges the two shapes without
placing encoded image bytes in tokenizer prompts.
"""

from __future__ import annotations

import base64
import binascii
import io
import re
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

SUPPORTED_IMAGE_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
MAX_IMAGES_PER_REQUEST = 4
MAX_REQUEST_IMAGE_BYTES = 24 * 1024 * 1024

_IMAGE_MARKER_RE = re.compile(
    r"<ovllm-image>(data:image/(?:jpeg|png|webp);base64,[A-Za-z0-9+/=]+)</ovllm-image>",
    re.IGNORECASE,
)
_CONTEXT_MARKER_RE = re.compile(r"\s*<ovllm-image-context:([A-Za-z0-9_-]{8,64})>\s*$")
_CONTEXT_TTL_SECONDS = 300
_CONTEXT_LIMIT = 64


@dataclass(frozen=True)
class ImagePayload:
    mime_type: str
    data: bytes
    width: int
    height: int


_context_lock = threading.Lock()
_contexts: OrderedDict[str, tuple[float, list[ImagePayload]]] = OrderedDict()


def backend_supports_vision(backend: str | None) -> bool:
    value = str(backend or "").lower()
    return "vlm" in value or "vision" in value


def capabilities_for_backend(backend: str | None) -> tuple[str, ...]:
    value = str(backend or "").lower()
    if "embedding" in value:
        return ("embeddings",)
    if backend_supports_vision(value):
        return ("chat", "vision")
    return ("chat",)


def _image_url_from_part(part: dict[str, Any]) -> str | None:
    part_type = str(part.get("type") or "").lower()
    if part_type not in {"image_url", "input_image"}:
        return None
    candidate: Any = part.get("image_url")
    if isinstance(candidate, dict):
        candidate = candidate.get("url")
    if not candidate and part_type == "input_image":
        candidate = part.get("file_data") or part.get("data")
    return candidate if isinstance(candidate, str) else None


def decode_data_url(url: str) -> ImagePayload:
    """Decode and verify one local image data URL.

    Remote URLs are deliberately rejected so the local API cannot become an SSRF-capable
    fetch proxy and the privacy boundary remains explicit.
    """

    if not isinstance(url, str) or not url.startswith("data:"):
        raise ValueError(
            "Image inputs must use a base64 data URL; remote image URLs are not fetched."
        )
    try:
        header, encoded = url.split(",", 1)
    except ValueError as exc:
        raise ValueError("Image data URL is malformed.") from exc

    metadata = header[5:].lower()
    pieces = [item.strip() for item in metadata.split(";") if item.strip()]
    mime_type = pieces[0] if pieces else ""
    if mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
        supported = ", ".join(sorted(SUPPORTED_IMAGE_MIME_TYPES))
        raise ValueError(f"Unsupported image type '{mime_type or 'unknown'}'. Use {supported}.")
    if "base64" not in pieces[1:]:
        raise ValueError("Image data URLs must be base64 encoded.")

    estimated_size = (len(encoded) * 3) // 4
    if estimated_size > MAX_IMAGE_BYTES + 3:
        raise ValueError(f"Each image must be {MAX_IMAGE_BYTES // (1024 * 1024)} MiB or smaller.")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Image data URL contains invalid base64 data.") from exc
    if not data:
        raise ValueError("Image input is empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError(f"Each image must be {MAX_IMAGE_BYTES // (1024 * 1024)} MiB or smaller.")

    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:  # pragma: no cover - declared dependency
        raise RuntimeError("Pillow is required for image validation.") from exc

    format_to_mime = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            actual_mime = format_to_mime.get(str(image.format or "").upper())
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("Image data could not be decoded as JPEG, PNG, or WebP.") from exc

    if actual_mime != mime_type:
        raise ValueError(
            f"Image content is {actual_mime or 'an unknown format'}, not the declared {mime_type}."
        )
    if width <= 0 or height <= 0:
        raise ValueError("Image dimensions must be positive.")
    if width * height > MAX_IMAGE_PIXELS:
        raise ValueError(f"Image exceeds the {MAX_IMAGE_PIXELS:,}-pixel safety limit.")
    return ImagePayload(mime_type=mime_type, data=data, width=width, height=height)


def validate_content(content: Any) -> Any:
    """Pydantic field validator for OpenAI-style message content."""

    if not isinstance(content, list):
        return content
    payloads: list[ImagePayload] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        url = _image_url_from_part(part)
        if url is not None:
            payloads.append(decode_data_url(url))
    if len(payloads) > MAX_IMAGES_PER_REQUEST:
        raise ValueError(f"A request may contain at most {MAX_IMAGES_PER_REQUEST} images.")
    if sum(len(payload.data) for payload in payloads) > MAX_REQUEST_IMAGE_BYTES:
        raise ValueError(
            f"Combined image data must be {MAX_REQUEST_IMAGE_BYTES // (1024 * 1024)} MiB or smaller."
        )
    return content


def content_to_transport_text(content: Any) -> str:
    """Flatten text parts and retain validated images as private transport markers."""

    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)

    parts: list[str] = []
    image_count = 0
    image_bytes = 0
    for item in content:
        if isinstance(item, str):
            parts.append(item)
            continue
        if not isinstance(item, dict):
            continue

        url = _image_url_from_part(item)
        if url is not None:
            payload = decode_data_url(url)
            image_count += 1
            image_bytes += len(payload.data)
            if image_count > MAX_IMAGES_PER_REQUEST:
                raise ValueError(f"A request may contain at most {MAX_IMAGES_PER_REQUEST} images.")
            if image_bytes > MAX_REQUEST_IMAGE_BYTES:
                raise ValueError(
                    f"Combined image data must be {MAX_REQUEST_IMAGE_BYTES // (1024 * 1024)} MiB or smaller."
                )
            parts.append(f"<ovllm-image>{url}</ovllm-image>")
            continue

        for key in ("text", "content", "value"):
            value = item.get(key)
            if isinstance(value, str):
                parts.append(value)
                break
    return "\n".join(parts)


def _purge_contexts_locked(now: float) -> None:
    expired = [key for key, (created, _) in _contexts.items() if now - created > _CONTEXT_TTL_SECONDS]
    for key in expired:
        _contexts.pop(key, None)
    while len(_contexts) >= _CONTEXT_LIMIT:
        _contexts.popitem(last=False)


def _store_context(payloads: list[ImagePayload]) -> str:
    key = uuid.uuid4().hex
    now = time.monotonic()
    with _context_lock:
        _purge_contexts_locked(now)
        _contexts[key] = (now, payloads)
    return key


def prepare_text_messages(messages: list[dict]) -> list[dict]:
    """Remove private image bytes before a text-only tokenizer sees messages."""

    prepared: list[dict] = []
    replacement = "[Image attached, but the selected model is not vision-capable.]"
    for message in messages:
        item = dict(message)
        content = str(item.get("content") or "")
        item["content"] = _IMAGE_MARKER_RE.sub(replacement, content)
        prepared.append(item)
    return prepared


def prepare_vision_messages(messages: list[dict]) -> tuple[list[dict], str | None]:
    """Replace private image markers with generic OpenVINO image tags."""

    payloads: list[ImagePayload] = []
    prepared: list[dict] = []
    for message in messages:
        item = dict(message)
        content = str(item.get("content") or "")

        def replace(match: re.Match[str]) -> str:
            if len(payloads) >= MAX_IMAGES_PER_REQUEST:
                raise ValueError(f"A request may contain at most {MAX_IMAGES_PER_REQUEST} images.")
            payloads.append(decode_data_url(match.group(1)))
            return f"<ov_genai_image_{len(payloads) - 1}>"

        item["content"] = _IMAGE_MARKER_RE.sub(replace, content)
        prepared.append(item)

    if not payloads:
        return prepared, None
    if sum(len(payload.data) for payload in payloads) > MAX_REQUEST_IMAGE_BYTES:
        raise ValueError(
            f"Combined image data must be {MAX_REQUEST_IMAGE_BYTES // (1024 * 1024)} MiB or smaller."
        )
    return prepared, _store_context(payloads)


def append_prompt_context(prompt: str, context_key: str | None) -> str:
    if not context_key:
        return prompt
    return f"{prompt}\n<ovllm-image-context:{context_key}>"


def strip_prompt_context(prompt: str) -> str:
    return _CONTEXT_MARKER_RE.sub("", prompt)


def discard_prompt_context(prompt: str) -> None:
    """Release an image context for a prompt rendered only for token budgeting."""

    match = _CONTEXT_MARKER_RE.search(prompt)
    if not match:
        return
    with _context_lock:
        _contexts.pop(match.group(1), None)


def consume_prompt_context(prompt: str) -> tuple[str, list[ImagePayload]]:
    """Remove a prompt context marker and return its image payloads exactly once."""

    match = _CONTEXT_MARKER_RE.search(prompt)
    if not match:
        return prompt, []
    clean_prompt = prompt[: match.start()].rstrip()
    key = match.group(1)
    with _context_lock:
        item = _contexts.pop(key, None)
    if item is None:
        raise RuntimeError("Image context expired before generation started. Retry the request.")
    return clean_prompt, item[1]


def to_openvino_tensors(payloads: list[ImagePayload]) -> list[Any]:
    """Convert validated encoded images to OpenVINO uint8 NHWC tensors."""

    if not payloads:
        return []
    try:
        import numpy as np
        from openvino import Tensor
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - real OpenVINO environments provide these
        raise RuntimeError("OpenVINO, NumPy, and Pillow are required for vision inference.") from exc

    tensors: list[Any] = []
    for payload in payloads:
        with Image.open(io.BytesIO(payload.data)) as image:
            rgb = image.convert("RGB")
            array = np.asarray(rgb, dtype=np.uint8)
        tensors.append(Tensor(array.reshape(1, array.shape[0], array.shape[1], 3)))
    return tensors
