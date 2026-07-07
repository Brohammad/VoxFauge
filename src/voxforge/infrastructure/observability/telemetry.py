from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from voxforge.config import Settings

_tracer_provider: TracerProvider | None = None


def setup_telemetry(settings: Settings) -> None:
    global _tracer_provider
    resource = Resource.create({"service.name": "voxforge"})
    _tracer_provider = TracerProvider(resource=resource)

    if settings.otel_exporter_otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
        _tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
    elif settings.app_env == "development":
        _tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(_tracer_provider)


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)
