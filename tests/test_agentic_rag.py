import asyncio
from types import SimpleNamespace

from insurance_chatbot.rag_service import (
    AgenticRAGService,
    OpenAIWebSearchService,
    PolicyDraftService,
    SourceChunk,
)
from insurance_chatbot.schemas import AskResponse, QueryMode


class FakeResponses:
    def __init__(self, response: SimpleNamespace) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return self.response


class FakeOpenAI:
    def __init__(self, response: SimpleNamespace) -> None:
        self.responses = FakeResponses(response)


class StubPolicyService:
    chat_model = "policy-model"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None, object]] = []

    async def query(
        self,
        question: str,
        policy_id: str | None = None,
        mode: object = QueryMode.POLICIES,
    ) -> AskResponse:
        self.calls.append((question, policy_id, mode))
        return AskResponse(
            answer="Policy answer [Fuente 1].",
            sources=["policy.pdf - Página 1"],
            metadata={"model": self.chat_model, "route": "policies"},
        )


class StubWebService:
    web_model = "web-model"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[str] = []

    async def query(self, question: str) -> AskResponse:
        self.calls.append(question)
        if self.fail:
            raise RuntimeError("web unavailable")
        return AskResponse(
            answer="Current web answer.",
            sources=["[Web] Regulator — https://example.com/news"],
            metadata={"model": self.web_model, "route": "web"},
        )


class StubAgent:
    def __init__(self, response: AskResponse | None = None, *, fail: bool = False) -> None:
        self.response = response
        self.fail = fail
        self.calls: list[dict[str, object]] = []

    async def ainvoke(self, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(payload)
        if self.fail:
            raise RuntimeError("router unavailable")
        assert self.response is not None
        return {
            "messages": [
                SimpleNamespace(type="tool", content=self.response.model_dump_json())
            ]
        }


def _agentic_service(
    *,
    agent: StubAgent,
    web_service: StubWebService | None = None,
) -> AgenticRAGService:
    return AgenticRAGService(
        policy_service=StubPolicyService(),  # type: ignore[arg-type]
        web_service=web_service or StubWebService(),  # type: ignore[arg-type]
        router_model="router-model",
        openai_api_key="test-key",
        agent=agent,
    )


def test_web_search_extracts_url_citations_and_uses_current_tool() -> None:
    annotation = SimpleNamespace(
        type="url_citation",
        url="https://example.com/regulator",
        title="Insurance regulator",
    )
    response = SimpleNamespace(
        id="resp-web",
        output_text="Recent insurance information with a citation.",
        output=[
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="output_text", annotations=[annotation])],
            )
        ],
    )
    client = FakeOpenAI(response)
    service = OpenAIWebSearchService(
        openai_client=client,  # type: ignore[arg-type]
        web_model="web-model",
        search_context_size="low",
    )

    result = asyncio.run(service.query("Recent insurance regulation"))

    assert result.sources == [
        "[Web] Insurance regulator — https://example.com/regulator"
    ]
    assert result.metadata["route"] == "web"
    call = client.responses.calls[0]
    assert call["tools"] == [{"type": "web_search", "search_context_size": "low"}]
    assert call["include"] == ["web_search_call.action.sources"]
    assert call["reasoning"] == {"effort": "low"}
    assert call["text"] == {"verbosity": "low"}
    assert call["max_output_tokens"] == 2000


def test_web_search_empty_output_returns_degraded_response() -> None:
    response = SimpleNamespace(id="resp-empty", output_text="", output=[])
    service = OpenAIWebSearchService(
        openai_client=FakeOpenAI(response),  # type: ignore[arg-type]
        web_model="web-model",
    )

    result = asyncio.run(service.query("Recent insurance regulation"))

    assert "No fue posible" in result.answer
    assert result.metadata["degraded"] is True
    assert result.metadata["route"] == "web"


def test_agent_route_returns_tool_contract() -> None:
    routed = AskResponse(
        answer="Web result",
        sources=["[Web] Source — https://example.com"],
        metadata={"route": "web"},
    )
    agent = StubAgent(routed)
    service = _agentic_service(agent=agent)

    result = asyncio.run(service.query("Latest insurance news", mode="auto"))

    assert result.answer == "Web result"
    assert result.metadata["router"] == "langchain_agent"
    assert result.metadata["router_model"] == "router-model"
    assert len(agent.calls) == 1


def test_agent_preserves_out_of_scope_route() -> None:
    routed = AskResponse(
        answer="Out of scope",
        sources=[],
        metadata={"route": "out_of_scope"},
    )
    service = _agentic_service(agent=StubAgent(routed))

    result = asyncio.run(service.query("Pizza recipe", mode="auto"))

    assert result.metadata["route"] == "out_of_scope"
    assert result.metadata["router"] == "langchain_agent"


def test_explicit_policy_mode_bypasses_agent() -> None:
    agent = StubAgent(fail=True)
    service = _agentic_service(agent=agent)

    result = asyncio.run(
        service.query("What does the policy cover?", "POL123", mode="policies")
    )

    assert result.metadata["route"] == "policies"
    assert result.metadata["router"] == "explicit"
    assert agent.calls == []


def test_agent_failure_uses_deterministic_combined_fallback() -> None:
    agent = StubAgent(fail=True)
    service = _agentic_service(agent=agent)

    result = asyncio.run(
        service.query("¿Qué noticia actual cambia esta póliza de seguro?", mode="auto")
    )

    assert result.metadata["route"] == "combined"
    assert result.metadata["router"] == "fallback"
    assert "Evidencia de pólizas" in result.answer
    assert "Información web actual" in result.answer


class StubRetrieval:
    embedding_model = "embedding-model"

    async def search(
        self,
        question: str,
        policy_id: str | None,
        top_k: int,
    ) -> list[SourceChunk]:
        return [
            SourceChunk(
                content=f"Coverage evidence for {policy_id}.",
                source_file=f"{policy_id}.pdf",
                page_number=2,
                article="ARTÍCULO 2",
            )
        ]


def test_policy_draft_is_grounded_and_traceable() -> None:
    response = SimpleNamespace(
        id="resp-draft",
        output_text="BORRADOR PARA REVISIÓN\nCobertura [Fuente 1].",
    )
    client = FakeOpenAI(response)
    service = PolicyDraftService(
        retrieval_service=StubRetrieval(),
        openai_client=client,  # type: ignore[arg-type]
        chat_model="draft-model",
    )

    result = asyncio.run(
        service.generate("Combine hospital coverage clauses", ["POL1", "POL2"])
    )

    assert result.draft.startswith("BORRADOR PARA REVISIÓN")
    assert result.metadata["source_policy_ids"] == ["POL1", "POL2"]
    assert result.metadata["retrieved_chunks"] == 2
    assert len(result.sources) == 2
    assert "Coverage evidence for POL1" in client.responses.calls[0]["input"]
