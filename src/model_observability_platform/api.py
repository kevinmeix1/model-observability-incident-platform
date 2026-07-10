from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from opentelemetry import propagate
from opentelemetry.trace import SpanKind, Status, StatusCode, format_trace_id
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.types import ASGIApp, Receive, Scope, Send

from .checks import run_checks
from .runtime_contract import (
    MODEL_NAME,
    SERVER_VERSION,
    EvaluationRequest,
    TransitionRequest,
)
from .runtime_metrics import RuntimeMetrics
from .runtime_state import (
    EvaluationConflict,
    IncidentNotFound,
    IncidentStore,
    InvalidTransition,
    TransitionConflict,
)
from .tracing import create_tracing

LOGGER = logging.getLogger("model_observability_platform.api")


@dataclass(frozen=True)
class Settings:
    state_root: Path = Path(".local")
    model_name: str = MODEL_NAME
    environment: str = "local"
    max_concurrency: int = 4
    queue_timeout_seconds: float = 0.25
    max_request_bytes: int = 2_000_000
    auto_resolve_after: int = 2
    trace_sample_ratio: float = 1.0
    capture_spans: bool = True
    otlp_endpoint: str | None = None

    def __post_init__(self) -> None:
        if self.model_name != MODEL_NAME:
            raise ValueError(f"model_name must be {MODEL_NAME}")
        if self.max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        if self.queue_timeout_seconds <= 0:
            raise ValueError("queue_timeout_seconds must be positive")
        if self.max_request_bytes < 1:
            raise ValueError("max_request_bytes must be positive")
        if self.auto_resolve_after < 1:
            raise ValueError("auto_resolve_after must be positive")
        if not 0 <= self.trace_sample_ratio <= 1:
            raise ValueError("trace_sample_ratio must be between zero and one")

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            state_root=Path(os.getenv("OBSERVABILITY_STATE_ROOT", ".local")),
            environment=os.getenv("DEPLOYMENT_ENVIRONMENT", "local"),
            max_concurrency=max(1, int(os.getenv("MAX_CONCURRENCY", "4"))),
            queue_timeout_seconds=max(0.01, float(os.getenv("QUEUE_TIMEOUT_SECONDS", "0.25"))),
            max_request_bytes=max(16_384, int(os.getenv("MAX_REQUEST_BYTES", "2000000"))),
            auto_resolve_after=max(1, int(os.getenv("AUTO_RESOLVE_AFTER", "2"))),
            trace_sample_ratio=max(0.0, min(float(os.getenv("TRACE_SAMPLE_RATIO", "1.0")), 1.0)),
            capture_spans=os.getenv("CAPTURE_SPANS", "true").lower() in {"1", "true", "yes"},
            otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or None,
        )


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "event": record.getMessage(),
        }
        for key in (
            "request_id",
            "trace_id",
            "method",
            "route",
            "status_code",
            "duration_ms",
            "evaluation_outcome",
            "incident_change_count",
            "error_category",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def configure_logging() -> None:
    if not any(getattr(handler, "observability_json", False) for handler in LOGGER.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonLogFormatter())
        handler.observability_json = True  # type: ignore[attr-defined]
        LOGGER.addHandler(handler)
    LOGGER.setLevel(os.getenv("LOG_LEVEL", "WARNING").upper())
    LOGGER.propagate = False


configure_logging()


class RequestBodyTooLarge(RuntimeError):
    pass


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError:
                await JSONResponse(
                    status_code=400,
                    content={"error": "invalid Content-Length header"},
                )(scope, receive, send)
                return
            if declared_size > self.max_bytes:
                await JSONResponse(
                    status_code=413,
                    content={"error": "request body exceeds the configured limit"},
                    headers={"Connection": "close"},
                )(scope, receive, send)
                return

        received = 0

        async def limited_receive() -> dict[str, Any]:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestBodyTooLarge:
            await JSONResponse(
                status_code=413,
                content={"error": "request body exceeds the configured limit"},
                headers={"Connection": "close"},
            )(scope, receive, send)


def route_key(method: str, path: str) -> str:
    del method
    if path in {
        "/",
        "/dashboard",
        "/health/live",
        "/health/ready",
        "/v1/runtime",
        "/v1/evaluations",
        "/v1/incidents",
        "/metrics",
        "/docs",
        "/openapi.json",
    }:
        return path
    if path.startswith("/v1/incidents/"):
        suffix = path.rsplit("/", 1)[-1]
        if suffix in {"events", "acknowledge", "resolve"}:
            return f"/v1/incidents/{{incident_id}}/{suffix}"
        return "/v1/incidents/{incident_id}"
    return "unmatched"


def trace_id() -> str:
    from opentelemetry.trace import get_current_span

    context = get_current_span().get_span_context()
    return format_trace_id(context.trace_id) if context.is_valid else "0" * 32


def fallback_dashboard() -> str:
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Model Observability Control Plane</title>
<style>
body{font-family:system-ui;margin:0;background:#f5f7fa;color:#172026}
main{max-width:760px;margin:64px auto;padding:28px}
h1{font-size:28px}a{color:#0f766e}
</style>
</head><body><main><h1>Model Observability Control Plane</h1>
<p>The API is ready. Run <code>make demo</code> to generate the full evidence dashboard.</p>
<p><a href="/docs">API contract</a> &middot;
<a href="/v1/runtime">Runtime state</a> &middot;
<a href="/metrics">Metrics</a></p>
</main></body></html>"""


def create_app(
    settings: Settings | None = None,
    *,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    clock = clock or (lambda: datetime.now(UTC))

    def runtime_now() -> datetime:
        value = clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise RuntimeError("runtime clock must return a timezone-aware value")
        return value.astimezone(UTC)

    store = IncidentStore(
        settings.state_root / "runtime" / "incidents.sqlite3",
        auto_resolve_after=settings.auto_resolve_after,
    )
    metrics = RuntimeMetrics()
    provider, tracer, span_exporter = create_tracing(
        service_version=SERVER_VERSION,
        environment=settings.environment,
        sample_ratio=settings.trace_sample_ratio,
        capture_spans=settings.capture_spans,
        otlp_endpoint=settings.otlp_endpoint,
    )
    concurrency = asyncio.Semaphore(settings.max_concurrency)
    metrics.refresh_incidents(store.summary())

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        provider.shutdown()

    app = FastAPI(
        title="Model Observability Incident Control Plane",
        version=SERVER_VERSION,
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=settings.max_request_bytes)
    app.state.settings = settings
    app.state.incident_store = store
    app.state.runtime_metrics = metrics
    app.state.tracer_provider = provider
    app.state.span_exporter = span_exporter

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": str(exc.detail)},
            headers=exc.headers or {},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        _: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        details = [
            {
                "location": ".".join(str(part) for part in error["loc"]),
                "message": error["msg"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": "request schema validation failed",
                "details": details,
            },
        )

    @app.exception_handler(EvaluationConflict)
    @app.exception_handler(TransitionConflict)
    @app.exception_handler(InvalidTransition)
    async def conflict_error(_: Request, exc: RuntimeError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"error": str(exc)})

    @app.exception_handler(IncidentNotFound)
    async def not_found_error(_: Request, exc: IncidentNotFound) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": f"incident not found: {exc}"},
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        route = route_key(request.method, request.url.path)
        started = time.perf_counter()
        status_code = 500
        response: Response | None = None
        parent_context = propagate.extract(dict(request.headers))
        attributes = {
            "http.request.method": request.method,
            "http.route": route,
            "url.scheme": request.url.scheme,
            "server.address": request.url.hostname or "unknown",
        }
        with tracer.start_as_current_span(
            f"{request.method} {route}",
            context=parent_context,
            kind=SpanKind.SERVER,
            attributes=attributes,
        ) as span:
            current_trace_id = trace_id()
            request.state.request_id = request_id
            request.state.trace_id = current_trace_id
            try:
                response = await call_next(request)
                status_code = response.status_code
                span.set_attribute("http.response.status_code", status_code)
                if status_code >= 500:
                    span.set_status(Status(StatusCode.ERROR))
                return response
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
                raise
            finally:
                duration = time.perf_counter() - started
                metrics.observe_http(
                    method=request.method,
                    route=route,
                    status_code=status_code,
                    duration_seconds=duration,
                )
                if response is not None:
                    response.headers["X-Request-ID"] = request_id
                    response.headers["X-Trace-ID"] = current_trace_id
                    response.headers["Server-Timing"] = f"app;dur={duration * 1000:.3f}"
                    response.headers["Cache-Control"] = "no-store"
                LOGGER.info(
                    "http_request_completed",
                    extra={
                        "request_id": request_id,
                        "trace_id": current_trace_id,
                        "method": request.method,
                        "route": route,
                        "status_code": status_code,
                        "duration_ms": round(duration * 1000, 3),
                    },
                )

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse("/dashboard", status_code=307)

    @app.get("/dashboard", include_in_schema=False)
    async def dashboard() -> Response:
        path = settings.state_root / "reports" / "model_observability_dashboard.html"
        if path.exists():
            return FileResponse(path, media_type="text/html")
        return HTMLResponse(fallback_dashboard())

    @app.get("/health/live")
    async def live() -> dict[str, bool]:
        return {"live": True}

    @app.get("/health/ready")
    async def ready() -> Response:
        is_ready = store.ready()
        return JSONResponse(
            status_code=200 if is_ready else 503,
            content={"ready": is_ready},
        )

    @app.get("/v1/runtime")
    async def runtime() -> dict[str, Any]:
        return {
            "service": "model-observability-control-plane",
            "version": SERVER_VERSION,
            "model_name": settings.model_name,
            "state_backend": "sqlite-wal",
            "idempotency": "evaluation-and-transition-keys",
            "auto_resolve_after": settings.auto_resolve_after,
            "telemetry": {
                "metrics": "prometheus",
                "traces": "opentelemetry",
                "logs": "structured-json",
            },
            "summary": store.summary(),
        }

    @app.post("/v1/evaluations")
    async def evaluate(
        body: EvaluationRequest,
        request: Request,
        response: Response,
    ) -> dict[str, Any]:
        acquired = False
        started = time.perf_counter()
        try:
            await asyncio.wait_for(
                concurrency.acquire(),
                timeout=settings.queue_timeout_seconds,
            )
            acquired = True
        except TimeoutError as exc:
            raise HTTPException(
                status_code=503,
                detail="evaluation concurrency limit reached",
                headers={"Retry-After": "1"},
            ) from exc

        try:
            payload = body.model_dump(mode="json")
            evaluated_at = runtime_now()
            with tracer.start_as_current_span(
                "model_observability.evaluate",
                attributes={
                    "ml.model.name": settings.model_name,
                    "model_observability.policy.version": body.policy_version,
                    "model_observability.reference.rows": len(body.reference_window),
                    "model_observability.current.rows": len(body.current_window),
                },
            ) as span:
                report = await asyncio.to_thread(
                    run_checks,
                    payload["reference_window"],
                    payload["current_window"],
                    now=evaluated_at,
                )
                result, replayed, changes = await asyncio.to_thread(
                    store.record_evaluation,
                    request_payload=payload,
                    report=report,
                    trace_id=request.state.trace_id,
                    created_at=evaluated_at.isoformat(),
                )
                span.set_attribute("model_observability.evaluation.passed", report["passed"])
                span.set_attribute(
                    "model_observability.failed_check.count",
                    sum(not check["passed"] for check in report["checks"]),
                )
                span.set_attribute("model_observability.idempotent_replay", replayed)
            duration = time.perf_counter() - started
            metrics.observe_evaluation(
                report,
                replayed=replayed,
                duration_seconds=duration,
            )
            if not replayed:
                for change in changes:
                    incident = store.get_incident(change["incident_id"])
                    metrics.observe_transition(
                        transition=change["change"],
                        severity=incident["severity"],
                    )
            metrics.refresh_incidents(store.summary())
            response.headers["X-Idempotent-Replay"] = str(replayed).lower()
            response.headers["X-Policy-Version"] = body.policy_version
            LOGGER.info(
                "evaluation_completed",
                extra={
                    "request_id": request.state.request_id,
                    "trace_id": request.state.trace_id,
                    "evaluation_outcome": "passed" if report["passed"] else "failed",
                    "incident_change_count": len(changes),
                    "duration_ms": round(duration * 1000, 3),
                },
            )
            return result
        finally:
            if acquired:
                concurrency.release()

    @app.get("/v1/incidents")
    async def incidents(
        status: str | None = Query(default=None),
        severity: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, Any]:
        try:
            items = store.list_incidents(
                status=status,
                severity=severity,
                limit=limit,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"count": len(items), "incidents": items}

    @app.get("/v1/incidents/{incident_id}")
    async def incident(incident_id: str) -> dict[str, Any]:
        return store.get_incident(incident_id)

    @app.get("/v1/incidents/{incident_id}/events")
    async def incident_events(
        incident_id: str,
        limit: int = Query(default=200, ge=1, le=500),
    ) -> dict[str, Any]:
        events = store.incident_events(incident_id, limit=limit)
        return {"count": len(events), "events": events}

    async def transition_incident(
        *,
        incident_id: str,
        target_status: str,
        body: TransitionRequest,
        request: Request,
        response: Response,
    ) -> dict[str, Any]:
        result, replayed = await asyncio.to_thread(
            store.transition,
            incident_id=incident_id,
            target_status=target_status,
            transition_id=body.transition_id,
            expected_version=body.expected_version,
            actor=body.actor,
            note=body.note,
            trace_id=request.state.trace_id,
            created_at=runtime_now().isoformat(),
        )
        if not replayed:
            metrics.observe_transition(
                transition=target_status,
                severity=result["incident"]["severity"],
            )
        metrics.refresh_incidents(store.summary())
        response.headers["X-Idempotent-Replay"] = str(replayed).lower()
        return result

    @app.post("/v1/incidents/{incident_id}/acknowledge")
    async def acknowledge(
        incident_id: str,
        body: TransitionRequest,
        request: Request,
        response: Response,
    ) -> dict[str, Any]:
        return await transition_incident(
            incident_id=incident_id,
            target_status="acknowledged",
            body=body,
            request=request,
            response=response,
        )

    @app.post("/v1/incidents/{incident_id}/resolve")
    async def resolve(
        incident_id: str,
        body: TransitionRequest,
        request: Request,
        response: Response,
    ) -> dict[str, Any]:
        return await transition_incident(
            incident_id=incident_id,
            target_status="resolved",
            body=body,
            request=request,
            response=response,
        )

    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics() -> Response:
        return Response(
            content=generate_latest(metrics.registry),
            media_type=CONTENT_TYPE_LATEST,
        )

    return app


app = create_app()
