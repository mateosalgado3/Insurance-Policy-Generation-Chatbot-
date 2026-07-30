"""Chainlit frontend for the Insurance Policy RAG API.

Responsibilities of this module are limited to UI orchestration: reading
user input, calling api_client, and rendering the response. All retrieval
and generation logic lives in the backend.
"""

from __future__ import annotations

import chainlit as cl

from api_client import (
    ApiResponseError,
    ApiTimeoutError,
    ApiUnavailableError,
    ask_question,
    check_readiness,
    fetch_config,
)

POLICY_ID_SESSION_KEY = "policy_id"
POLICY_COMMAND_PREFIX = "/policy"
POLICY_CLEAR_ARGUMENT = "clear"
CONFIG_COMMAND = "/config"


def _format_sources(sources: list[str]) -> list[cl.Text]:
    """Build one Chainlit element per source so they render as separate cards."""
    return [
        cl.Text(name=f"Source {index}", content=source, display="inline")
        for index, source in enumerate(sources, start=1)
    ]


def _parse_policy_command(text: str) -> str | None:
    """Return the policy id argument if text is a /policy command, else None.

    An empty string is returned for '/policy clear', signaling the caller
    to remove the stored policy id.
    """
    stripped = text.strip()
    if not stripped.lower().startswith(POLICY_COMMAND_PREFIX):
        return None

    argument = stripped[len(POLICY_COMMAND_PREFIX):].strip()
    if argument.lower() == POLICY_CLEAR_ARGUMENT:
        return ""
    return argument


def _format_readiness(readiness) -> str:
    if readiness is None:
        return (
            "Backend status: unreachable. Questions will fail until the "
            "API at the configured URL is reachable."
        )

    if readiness.status == "ready":
        return f"Backend status: ready ({readiness.indexed_chunks} indexed chunks)."

    reason = readiness.detail or "reason not reported"
    return f"Backend status: not ready ({reason})."


@cl.on_chat_start
async def on_chat_start() -> None:
    readiness = await check_readiness()
    cl.user_session.set(POLICY_ID_SESSION_KEY, None)

    await cl.Message(
        content=(
            f"{_format_readiness(readiness)}\n\n"
            "Ask a question about an insurance policy to get started.\n"
            "Optional commands:\n"
            "- `/policy <id>` to scope questions to a specific policy\n"
            "- `/policy clear` to remove that scope\n"
            "- `/config` to show the active model and index configuration"
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    if message.content.strip().lower() == CONFIG_COMMAND:
        config = await fetch_config()
        if config is None:
            await cl.Message(content="Could not reach the backend /config endpoint.").send()
            return
        await cl.Message(
            content=(
                f"LLM model: {config.llm_model}\n"
                f"Embedding model: {config.embedding_model}\n"
                f"Vector store: {config.vector_store}\n"
                f"Collection: {config.collection}\n"
                f"Top k: {config.top_k}\n"
                f"Score threshold: {config.score_threshold}\n"
                f"OpenAI configured: {config.openai_configured}"
            )
        ).send()
        return

    policy_argument = _parse_policy_command(message.content)
    if policy_argument is not None:
        stored_value = policy_argument or None
        cl.user_session.set(POLICY_ID_SESSION_KEY, stored_value)
        confirmation = (
            f"Policy id set to: {stored_value}"
            if stored_value
            else "Policy id cleared. Questions will search across all policies."
        )
        await cl.Message(content=confirmation).send()
        return

    question = message.content.strip()
    if not question:
        await cl.Message(content="Please type a question.").send()
        return

    policy_id = cl.user_session.get(POLICY_ID_SESSION_KEY)

    loading_message = cl.Message(content="Looking up the policy documents...")
    await loading_message.send()

    try:
        result = await ask_question(question=question, policy_id=policy_id)
    except ApiTimeoutError:
        loading_message.content = (
            "The backend took too long to respond. Please try again."
        )
        await loading_message.update()
        return
    except ApiUnavailableError:
        loading_message.content = (
            "The backend is unreachable right now. Confirm the API is "
            "running and the configured URL is correct."
        )
        await loading_message.update()
        return
    except ApiResponseError as exc:
        loading_message.content = f"The backend returned an error: {exc.detail}"
        await loading_message.update()
        return

    loading_message.content = result.answer
    loading_message.elements = _format_sources(result.sources)
    await loading_message.update()