"""FastAPI routes for the packaged desktop first-run workflow."""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.config import Settings
from app.onboarding_models import (
    CancelPreparationResponse,
    CompleteOnboardingRequest,
    ConnectionConfigurationResponse,
    ModelRecommendationResponse,
    NpuReadinessResponse,
    OnboardingStatusResponse,
    PreparationProgressResponse,
    PrepareModelRequest,
    RestartOnboardingResponse,
    SystemScanResponse,
)
from app.onboarding_service import OnboardingService


def _state_change_auth(settings: Settings):
    async def require_key(authorization: str | None = Header(default=None)) -> None:
        configured = [item.strip() for item in (settings.api_key or "").split(",") if item.strip()]
        if not configured:
            return
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
        supplied = authorization.removeprefix("Bearer ")
        if not any(secrets.compare_digest(supplied, key) for key in configured):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    return require_key


def _bad_request(exc: Exception) -> HTTPException:
    message = str(exc).strip() or "The onboarding request could not be completed."
    return HTTPException(status_code=400, detail=message[:300])


def register_onboarding_routes(
    app: Any,
    *,
    service: OnboardingService,
    settings: Settings,
    instance_nonce: str,
) -> None:
    router = APIRouter(prefix="/v1/onboarding", tags=["onboarding"])
    mutation_auth = [Depends(_state_change_auth(settings))]

    @app.get("/desktop/instance", include_in_schema=False)
    async def desktop_instance():
        return {
            "application": "OpenVINO Windows LLM",
            "instance_nonce": instance_nonce,
            "port": service.endpoint_port,
        }

    @app.post("/desktop/shutdown", include_in_schema=False)
    async def desktop_shutdown(x_instance_nonce: str | None = Header(default=None)):
        if not x_instance_nonce or not secrets.compare_digest(x_instance_nonce, instance_nonce):
            raise HTTPException(status_code=403, detail="Invalid desktop instance token")
        callback = getattr(app.state, "shutdown_callback", None)
        if callback is None:
            raise HTTPException(status_code=409, detail="Desktop shutdown is unavailable")
        import asyncio

        asyncio.get_running_loop().call_later(0.2, callback)
        return {"status": "shutting_down"}

    @router.get("/documentation", include_in_schema=False)
    async def onboarding_documentation():
        return RedirectResponse(
            "https://github.com/Quazmoz/openvino-windows-llm/blob/main/docs/FIRST_RUN.md",
            status_code=307,
        )

    @router.get("/status", response_model=OnboardingStatusResponse)
    async def onboarding_status():
        return service.status()

    @router.get("/system-scan", response_model=SystemScanResponse)
    async def onboarding_system_scan(refresh: bool = Query(default=False)):
        try:
            return await _off_thread(service.system_scan, refresh=refresh)
        except Exception as exc:
            raise _bad_request(exc) from exc

    @router.get("/npu-readiness", response_model=NpuReadinessResponse)
    async def onboarding_npu_readiness(refresh: bool = Query(default=False)):
        try:
            return await _off_thread(service.npu_readiness, refresh=refresh)
        except Exception as exc:
            raise _bad_request(exc) from exc

    @router.get("/recommendation", response_model=ModelRecommendationResponse)
    async def onboarding_recommendation(refresh: bool = Query(default=False)):
        try:
            return await _off_thread(service.recommendation, refresh=refresh)
        except Exception as exc:
            raise _bad_request(exc) from exc

    @router.post(
        "/prepare",
        response_model=PreparationProgressResponse,
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=mutation_auth,
    )
    async def onboarding_prepare(request: PrepareModelRequest):
        try:
            return await service.start_preparation(request)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)[:300]) from exc
        except (KeyError, ValueError) as exc:
            raise _bad_request(exc) from exc

    @router.get("/preparation/{job_id}", response_model=PreparationProgressResponse)
    async def onboarding_preparation(job_id: str):
        try:
            return service.progress(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post(
        "/preparation/{job_id}/cancel",
        response_model=CancelPreparationResponse,
        dependencies=mutation_auth,
    )
    async def onboarding_cancel(job_id: str):
        try:
            return await service.cancel(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post(
        "/complete",
        response_model=ConnectionConfigurationResponse,
        dependencies=mutation_auth,
    )
    async def onboarding_complete(request: CompleteOnboardingRequest):
        try:
            return service.complete(request.job_id)
        except (KeyError, ValueError) as exc:
            raise _bad_request(exc) from exc

    @router.post(
        "/restart",
        response_model=RestartOnboardingResponse,
        dependencies=mutation_auth,
    )
    async def onboarding_restart():
        return service.restart()

    @router.get("/connection", response_model=ConnectionConfigurationResponse)
    async def onboarding_connection():
        try:
            return service.connection_configuration()
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    app.include_router(router)


async def _off_thread(function, /, **kwargs):
    import asyncio

    return await asyncio.to_thread(function, **kwargs)
