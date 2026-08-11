import asyncio
import json
from typing import Any

import httpx

from frontend import api_client
from frontend.app import (
    _extract_policy_id,
    _format_response_context,
    _format_sources,
    _parse_draft_command,
    _parse_mode_command,
    _parse_policy_command,
)


def _mock_async_client(monkeypatch, handler):
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(api_client.httpx, "AsyncClient", factory)


def test_command_parsers() -> None:
    assert _parse_policy_command("/policy POL123") == "POL123"
    assert _parse_policy_command("/policy clear") == ""
    assert _parse_mode_command("/mode COMBINED") == "combined"
    assert _parse_draft_command("/draft POL1, POL2 | Combine coverage") == (
        ["POL1", "POL2"],
        "Combine coverage",
    )
    assert _parse_draft_command("normal question") is None
    assert _extract_policy_id("Summarize policy POL320190074 please") == "POL320190074"
    assert _extract_policy_id("What are the exclusions?") is None


def test_sources_render_inline_without_chainlit_file_elements() -> None:
    rendered = _format_sources(
        ["POL1.pdf - Página 4", "[Web] Regulator — https://example.com"]
    )

    assert "### Fuentes consultadas" in rendered
    assert "**Fuente 1:** POL1.pdf - Página 4" in rendered
    assert "**Web 1:** [Regulator](https://example.com)" in rendered
    assert _format_sources([]) == ""


def test_sources_group_web_links_and_context_badges() -> None:
    rendered = _format_sources(
        ["POL1.pdf - Página 4", "[Web] Regulator — https://example.com"]
    )
    context = _format_response_context(
        {
            "route": "policies",
            "response_time_ms": 1250,
            "latency_ms": {
                "time_to_model_ms": 250,
                "model_response_time_ms": 990,
            },
        },
        "auto",
        "POL1",
    )

    assert "**Documentos**" in rendered
    assert "[Regulator](https://example.com)" in rendered
    assert "📚 Pólizas" in context
    assert "1.2s" in context
    assert "Hasta modelo" in context
    assert "Modelo" in context


def test_ask_client_sends_mode_and_policy(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "answer": "answer",
                "sources": ["source"],
                "metadata": {"route": "combined"},
            },
        )

    _mock_async_client(monkeypatch, handler)
    result = asyncio.run(api_client.ask_question("question", "POL1", "combined"))

    assert captured == {
        "question": "question",
        "policy_id": "POL1",
        "mode": "combined",
    }
    assert result.metadata["route"] == "combined"


def test_readiness_parses_503_body(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            json={
                "status": "not_ready",
                "openai_configured": False,
                "index_ready": True,
                "collection": "policies",
                "indexed_chunks": 262,
                "detail": "OPENAI_API_KEY is not configured",
            },
        )

    _mock_async_client(monkeypatch, handler)
    result = asyncio.run(api_client.check_readiness())

    assert result is not None
    assert result.status == "not_ready"
    assert result.indexed_chunks == 262


def test_draft_client_parses_contract(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "draft": "BORRADOR",
                "sources": ["POL1.pdf"],
                "metadata": {"source_policy_ids": ["POL1"]},
                "disclaimer": "Review required",
            },
        )

    _mock_async_client(monkeypatch, handler)
    result = asyncio.run(
        api_client.generate_policy_draft("Create hospital coverage", ["POL1"])
    )

    assert result.draft == "BORRADOR"
    assert result.disclaimer == "Review required"


def test_stream_client_parses_sse_contract(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/ask/stream"
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=(
                'event: status\ndata: {"message":"Searching"}\n\n'
                'event: token\ndata: {"text":"Hello"}\n\n'
                'event: complete\ndata: {"sources":[],"metadata":{"route":"web"}}\n\n'
            ),
        )

    async def collect_events():
        return [
            event
            async for event in api_client.stream_question("question", None, "web")
        ]

    _mock_async_client(monkeypatch, handler)
    events = asyncio.run(collect_events())

    assert [event.event for event in events] == ["status", "token", "complete"]
    assert events[1].data["text"] == "Hello"
