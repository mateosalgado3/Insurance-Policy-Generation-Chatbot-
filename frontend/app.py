"""Chainlit frontend for the Insurance Policy RAG API.

Responsibilities of this module are limited to UI orchestration: reading
user input, calling api_client, and rendering the response. All retrieval
and generation logic lives in the backend.
"""

from __future__ import annotations

import chainlit as cl

from frontend.api_client import (
    ApiResponseError,
    ApiTimeoutError,
    ApiUnavailableError,
    ask_question,
    check_readiness,
    fetch_config,
    generate_policy_draft,
)

POLICY_ID_SESSION_KEY = "policy_id"
MODE_SESSION_KEY = "query_mode"
POLICY_COMMAND_PREFIX = "/policy"
POLICY_CLEAR_ARGUMENT = "clear"
MODE_COMMAND_PREFIX = "/mode"
VALID_MODES = {"auto", "policies", "web", "combined"}
DRAFT_COMMAND_PREFIX = "/draft"
CONFIG_COMMAND = "/config"


def _format_sources(sources: list[str]) -> str:
    """Render sources inline so they do not depend on temporary file storage."""
    if not sources:
        return ""
    items = "\n".join(
        f"- **Fuente {index}:** {source}"
        for index, source in enumerate(sources, start=1)
    )
    return f"\n\n### Fuentes consultadas\n\n{items}"


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


def _parse_mode_command(text: str) -> str | None:
    stripped = text.strip()
    if not stripped.lower().startswith(MODE_COMMAND_PREFIX):
        return None
    return stripped[len(MODE_COMMAND_PREFIX):].strip().lower()


def _parse_draft_command(text: str) -> tuple[list[str], str] | None:
    stripped = text.strip()
    if not stripped.lower().startswith(DRAFT_COMMAND_PREFIX):
        return None
    argument = stripped[len(DRAFT_COMMAND_PREFIX):].strip()
    if "|" not in argument:
        return ([], "")
    policy_part, instructions = argument.split("|", maxsplit=1)
    policy_ids = [item.strip() for item in policy_part.split(",") if item.strip()]
    return policy_ids, instructions.strip()


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
    cl.user_session.set(MODE_SESSION_KEY, "auto")

    await cl.Message(
        content=(
            f"{_format_readiness(readiness)}\n\n"
            "Ask a question about an insurance policy to get started.\n"
            "Optional commands:\n"
            "- `/policy <id>` to scope questions to a specific policy\n"
            "- `/policy clear` to remove that scope\n"
            "- `/mode auto|policies|web|combined` to choose the route\n"
            "- `/draft POL1,POL2 | instructions` to create a review-only draft\n"
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
                f"Router model: {config.router_model}\n"
                f"Web model: {config.web_model}\n"
                f"Embedding model: {config.embedding_model}\n"
                f"Vector store: {config.vector_store}\n"
                f"Collection: {config.collection}\n"
                f"Top k: {config.top_k}\n"
                f"Score threshold: {config.score_threshold}\n"
                f"Available modes: {', '.join(config.available_modes)}\n"
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

    mode_argument = _parse_mode_command(message.content)
    if mode_argument is not None:
        if mode_argument not in VALID_MODES:
            await cl.Message(
                content="Invalid mode. Use: auto, policies, web, or combined."
            ).send()
            return
        cl.user_session.set(MODE_SESSION_KEY, mode_argument)
        await cl.Message(content=f"Query mode set to: {mode_argument}").send()
        return

    draft_argument = _parse_draft_command(message.content)
    if draft_argument is not None:
        policy_ids, instructions = draft_argument
        if not 1 <= len(policy_ids) <= 3 or len(instructions) < 10:
            await cl.Message(
                content=(
                    "Use `/draft POL1,POL2 | instructions` with one to three policy "
                    "ids and at least 10 characters of instructions."
                )
            ).send()
            return
        loading_message = cl.Message(content="Generating a traceable review-only draft...")
        await loading_message.send()
        try:
            result = await generate_policy_draft(instructions, policy_ids)
        except (ApiTimeoutError, ApiUnavailableError, ApiResponseError) as exc:
            loading_message.content = f"Could not generate the draft: {exc}"
            await loading_message.update()
            return
        loading_message.content = (
            f"{result.draft}\n\n---\n{result.disclaimer}"
            f"{_format_sources(result.sources)}"
        )
        await loading_message.update()
        return

    question = message.content.strip()
    if not question:
        await cl.Message(content="Please type a question.").send()
        return

    policy_id = cl.user_session.get(POLICY_ID_SESSION_KEY)
    mode = cl.user_session.get(MODE_SESSION_KEY) or "auto"

    loading_message = cl.Message(content="Looking up the policy documents...")
    await loading_message.send()

    try:
        result = await ask_question(question=question, policy_id=policy_id, mode=mode)
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

    route = result.metadata.get("route", mode)
    loading_message.content = (
        f"{result.answer}\n\n---\nRoute: `{route}`"
        f"{_format_sources(result.sources)}"
    )
    await loading_message.update()
