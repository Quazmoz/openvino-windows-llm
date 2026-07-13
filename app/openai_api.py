"""OpenAI-compatible request/response models (Pydantic v2).

These mirror the subset of the OpenAI API the server implements: chat
completions (with streaming + tool calling) and the Responses API used by tools
like n8n. They are plain data models with no OpenVINO dependency.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from runtime import device_check

# --- Chat messages ---------------------------------------------------------


class ChatMessage(BaseModel):
    role: str
    content: Any = None  # str, list of content parts, or None (OpenAI spec allows all three)
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


# --- Tool / function calling ----------------------------------------------


class FunctionDefinition(BaseModel):
    name: str
    description: str | None = None
    parameters: dict[str, Any] | None = None


class ToolDefinition(BaseModel):
    type: str = "function"
    function: FunctionDefinition


class FunctionCall(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str
    type: str = "function"
    function: FunctionCall


# --- Chat completions ------------------------------------------------------


class StreamOptions(BaseModel):
    include_usage: bool | None = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage] = Field(min_length=1)
    max_tokens: int | None = Field(default=512, ge=1)
    temperature: float | None = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float | None = Field(default=1.0, ge=0.0, le=1.0)
    stream: bool | None = False
    stream_options: StreamOptions | None = None
    tools: list[ToolDefinition] | None = None
    tool_choice: Any | None = None  # "auto" | "none" | "required" | {type, function}
    stop: str | list[str] | None = None  # stop sequence(s) that end generation
    seed: int | None = None  # seed the sampler for reproducible output (best effort)
    response_format: dict[str, Any] | None = None  # JSON object or JSON Schema constraint
    lora_path: str | None = None  # path to safetensors LoRA weights
    lora_alpha: float | None = Field(default=1.0, gt=0.0)


class ChatCompletionMessage(BaseModel):
    role: str
    content: str | None = None
    tool_calls: list[ToolCall] | None = None


class ChatCompletionResponseChoice(BaseModel):
    index: int
    message: ChatCompletionMessage
    finish_reason: str


class UsageInfo(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionResponseChoice]
    usage: UsageInfo | None = None


# --- Responses API (n8n compatibility) ------------------------------------


class ResponseRequest(BaseModel):
    model: str
    input: Any  # string or list of {role, content} messages
    instructions: str | None = None
    max_output_tokens: int | None = Field(default=512, ge=1)
    temperature: float | None = Field(default=0.7, ge=0.0, le=2.0)
    stream: bool | None = False
    lora_path: str | None = None
    lora_alpha: float | None = Field(default=1.0, gt=0.0)


class ResponseOutputMessage(BaseModel):
    type: str = "message"
    id: str
    status: str = "completed"
    role: str = "assistant"
    content: list[dict[str, Any]]


class ResponseObject(BaseModel):
    id: str
    object: str = "response"
    created_at: int
    model: str
    output: list[ResponseOutputMessage]
    status: str = "completed"


# --- Model lifecycle requests ---------------------------------------------


class ModelLoadRequest(BaseModel):
    model: str
    device: str | None = None  # override the server default device for this load
    draft_model: str | None = (
        None  # catalog model id or path to draft model for speculative decoding
    )


class ModelConvertRequest(BaseModel):
    model: str
    device: str | None = None  # optional device to use if loading after conversion
    load_after: bool = True
    weight_format: str | None = Field(default=None, pattern=r"^(int4|int8|fp16)$")
    group_size: int | None = Field(default=None, ge=-1)
    ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    sym: bool | None = None


class ModelUnloadRequest(BaseModel):
    model: str


class ModelDeleteRequest(BaseModel):
    model: str


class ModelRegisterRequest(BaseModel):
    model_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
        description="Filesystem-safe model identifier, for example smollm2-135m-int4.",
    )
    name: str = Field(min_length=1, max_length=160)
    source_model: str = Field(min_length=1, max_length=240)
    weight_format: str = Field(default="int4", pattern=r"^(int4|int8|fp16)$")
    recommended_device: str = Field(default="NPU", min_length=1, max_length=64)
    max_context_len: int = Field(default=2048, ge=128, le=262144)
    max_output_tokens: int = Field(default=512, ge=1, le=65536)
    description: str | None = None

    @field_validator("recommended_device")
    @classmethod
    def validate_recommended_device(cls, value: str) -> str:
        try:
            return device_check.validate_device_expression(value)
        except device_check.DeviceValidationError as exc:
            raise ValueError(str(exc)) from exc


# --- Benchmark requests ---------------------------------------------------


class BenchmarkRunRequest(BaseModel):
    model: str | None = None
    models: list[str] | None = None
    devices: list[str] = Field(default_factory=lambda: ["CPU", "GPU", "NPU", "AUTO"])
    prompt: str | None = None
    max_tokens: int = Field(default=64, ge=1, le=4096)
    runs: int = Field(default=1, ge=1, le=10)


# --- Conversation export --------------------------------------------------


class ChatExportRequest(BaseModel):
    messages: list[ChatMessage]
    model: str | None = None
    device: str | None = None


# --- Embeddings -----------------------------------------------------------


class EmbeddingRequest(BaseModel):
    model: str
    input: str | list[str]
    user: str | None = None
    encoding_format: str | None = Field(default="float", pattern=r"^(float|base64)$")


class EmbeddingResponseData(BaseModel):
    object: str = "embedding"
    index: int
    embedding: list[float] | str


class EmbeddingResponseUsage(BaseModel):
    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: list[EmbeddingResponseData]
    model: str
    usage: EmbeddingResponseUsage


class DownloadCustomRequest(BaseModel):
    model_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
        description="Filesystem-safe model identifier, for example smollm2-135m-int4.",
    )
    name: str = Field(min_length=1, max_length=160)
    source_model: str = Field(min_length=1, max_length=240)
    backend: str = Field(
        default="openvino-genai", pattern=r"^(openvino-genai|openvino-embeddings)$"
    )
    weight_format: str = Field(default="int4", pattern=r"^(int4|int8|fp16)$")
    group_size: int | None = Field(default=None, ge=-1)
    ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    sym: bool | None = None
    recommended_device: str = Field(default="CPU", min_length=1, max_length=64)
    max_context_len: int = Field(default=2048, ge=128, le=262144)
    max_output_tokens: int = Field(default=512, ge=0, le=65536)
    description: str | None = None
    load_after: bool = True

    @field_validator("recommended_device")
    @classmethod
    def validate_recommended_device(cls, value: str) -> str:
        try:
            return device_check.validate_device_expression(value)
        except device_check.DeviceValidationError as exc:
            raise ValueError(str(exc)) from exc
