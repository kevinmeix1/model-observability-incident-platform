from __future__ import annotations

import threading
from collections import deque
from collections.abc import Sequence

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from opentelemetry.trace import Tracer


class BoundedSpanExporter(SpanExporter):
    def __init__(self, capacity: int = 200) -> None:
        self._spans: deque[ReadableSpan] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        with self._lock:
            self._spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        del timeout_millis
        return True

    def finished_spans(self) -> tuple[ReadableSpan, ...]:
        with self._lock:
            return tuple(self._spans)


def create_tracing(
    *,
    service_version: str,
    environment: str,
    sample_ratio: float,
    capture_spans: bool,
    otlp_endpoint: str | None,
) -> tuple[TracerProvider, Tracer, BoundedSpanExporter | None]:
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": "model-observability-control-plane",
                "service.version": service_version,
                "deployment.environment.name": environment,
            }
        ),
        sampler=TraceIdRatioBased(max(0.0, min(sample_ratio, 1.0))),
    )
    capture = BoundedSpanExporter() if capture_spans else None
    if capture is not None:
        provider.add_span_processor(SimpleSpanProcessor(capture))
    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint)))
    return (
        provider,
        provider.get_tracer("model_observability_platform.api", service_version),
        capture,
    )
