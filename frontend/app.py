"""Friendly Chainlit UI for the Insurance Policy RAG API."""

from __future__ import annotations

import asyncio
import re
from typing import Any

import chainlit as cl
from chainlit.input_widget import Select, TextInput

from frontend.api_client import (
    ApiResponseError,
    ApiTimeoutError,
    ApiUnavailableError,
    check_readiness,
    fetch_config,
    generate_policy_draft,
    stream_question,
)
from frontend.config import STREAM_RENDER_DELAY_SECONDS

POLICY_ID_SESSION_KEY = "policy_id"
MODE_SESSION_KEY = "query_mode"
POLICY_COMMAND_PREFIX = "/policy"
POLICY_CLEAR_ARGUMENT = "clear"
MODE_COMMAND_PREFIX = "/mode"
VALID_MODES = {"auto", "policies", "web", "combined"}
DRAFT_COMMAND_PREFIX = "/draft"
CONFIG_COMMAND = "/config"
READY_COMMAND = "/ready"
HELP_COMMAND = "/help"

MODE_LABELS = {
    "auto": "✨ Automático",
    "policies": "📚 Pólizas",
    "web": "🌐 Web actual",
    "combined": "🔀 Combinado",
    "out_of_scope": "🛡️ Fuera de alcance",
}
DRAFT_LABEL = "📝 Borrador"
POLICY_ID_PATTERN = re.compile(r"\bPOL\d{9,12}\b", re.IGNORECASE)


def _format_sources(sources: list[str]) -> str:
    """Group policy and web sources in a readable, traceable list."""
    if not sources:
        return ""

    policy_sources = [source for source in sources if not source.startswith("[Web]")]
    web_sources = [source for source in sources if source.startswith("[Web]")]
    sections: list[str] = ["\n\n### Fuentes consultadas"]

    if policy_sources:
        sections.append("\n**Documentos**")
        sections.extend(
            f"- **Fuente {index}:** {source}"
            for index, source in enumerate(policy_sources, start=1)
        )

    if web_sources:
        sections.append("\n**Fuentes web**")
        for index, source in enumerate(web_sources, start=1):
            clean_source = source.removeprefix("[Web] ")
            if " — " in clean_source:
                title, url = clean_source.rsplit(" — ", maxsplit=1)
                sections.append(f"- **Web {index}:** [{title}]({url})")
            else:
                sections.append(f"- **Web {index}:** {clean_source}")

    return "\n".join(sections)


def _format_response_context(
    metadata: dict[str, Any],
    requested_mode: str,
    policy_id: str | None,
) -> str:
    route = str(metadata.get("route", requested_mode))
    route_label = DRAFT_LABEL if route == "draft" else MODE_LABELS.get(route, route)
    labels = [f"**Ruta:** {route_label}"]
    if policy_id:
        labels.append(f"**Póliza:** `{policy_id}`")
    latency = metadata.get("latency_ms")
    if isinstance(latency, dict):
        time_to_model = latency.get("time_to_model_ms")
        model_response = latency.get("model_response_time_ms")
        parallel = latency.get("parallel_components")
        if isinstance(parallel, dict):
            component_latencies = [item for item in parallel.values() if isinstance(item, dict)]
            if not isinstance(time_to_model, (int, float)):
                pre_model_values = [
                    item["time_to_model_ms"]
                    for item in component_latencies
                    if isinstance(item.get("time_to_model_ms"), (int, float))
                ]
                time_to_model = max(pre_model_values, default=None)
            if not isinstance(model_response, (int, float)):
                model_values = [
                    item["model_response_time_ms"]
                    for item in component_latencies
                    if isinstance(item.get("model_response_time_ms"), (int, float))
                ]
                model_response = max(model_values, default=None)
        if isinstance(time_to_model, (int, float)):
            labels.append(f"**Hasta modelo:** {time_to_model / 1000:.1f}s")
        if isinstance(model_response, (int, float)):
            labels.append(f"**Modelo:** {model_response / 1000:.1f}s")
    response_time = metadata.get("response_time_ms")
    if isinstance(response_time, (int, float)):
        labels.append(f"**Total:** {response_time / 1000:.1f}s")
    if metadata.get("degraded"):
        labels.append("**Estado:** respuesta web limitada")
    return "\n\n---\n" + " · ".join(labels)


def _mode_actions() -> list[cl.Action]:
    return [
        cl.Action(
            name="set_mode",
            payload={"mode": mode},
            label=label,
            tooltip=f"Usar modo {mode}",
        )
        for mode, label in MODE_LABELS.items()
        if mode in VALID_MODES
    ]


def _parse_policy_command(text: str) -> str | None:
    stripped = text.strip()
    if not stripped.lower().startswith(POLICY_COMMAND_PREFIX):
        return None
    argument = stripped[len(POLICY_COMMAND_PREFIX) :].strip()
    if argument.lower() == POLICY_CLEAR_ARGUMENT:
        return ""
    return argument


def _extract_policy_id(text: str) -> str | None:
    """Use an explicit policy ID in the question as a one-request filter."""
    match = POLICY_ID_PATTERN.search(text)
    return match.group(0).upper() if match else None


def _parse_mode_command(text: str) -> str | None:
    stripped = text.strip()
    if not stripped.lower().startswith(MODE_COMMAND_PREFIX):
        return None
    return stripped[len(MODE_COMMAND_PREFIX) :].strip().lower()


def _parse_draft_command(text: str) -> tuple[list[str], str] | None:
    stripped = text.strip()
    if not stripped.lower().startswith(DRAFT_COMMAND_PREFIX):
        return None
    argument = stripped[len(DRAFT_COMMAND_PREFIX) :].strip()
    if "|" not in argument:
        return ([], "")
    policy_part, instructions = argument.split("|", maxsplit=1)
    policy_ids = [item.strip() for item in policy_part.split(",") if item.strip()]
    return policy_ids, instructions.strip()


def _format_readiness(readiness: Any) -> str:
    if readiness is None:
        return "🔴 Backend no disponible"
    if readiness.status == "ready":
        return f"🟢 RAG listo · {readiness.indexed_chunks} chunks indexados"
    reason = readiness.detail or "motivo no informado"
    return f"🟠 RAG no disponible · {reason}"


def _help_text() -> str:
    return (
        "### Comandos rápidos\n\n"
        "- `/ready` — verificar el estado del RAG\n"
        "- `/config` — ver la configuración pública\n"
        "- `/mode auto|policies|web|combined` — cambiar la ruta\n"
        "- `/policy POL320190074` — limitar la búsqueda a una póliza\n"
        "- `/policy clear` — buscar nuevamente en todo el corpus\n"
        "- `/draft POL320190074 | instrucciones` — crear un borrador trazable"
    )


async def _send_settings() -> None:
    await cl.ChatSettings(
        [
            Select(
                id="mode",
                label="Modo de consulta",
                items={
                    "✨ Automático": "auto",
                    "📚 Solo pólizas": "policies",
                    "🌐 Web actual": "web",
                    "🔀 Pólizas + web": "combined",
                },
                initial_value=cl.user_session.get(MODE_SESSION_KEY) or "auto",
                description="Selecciona dónde debe buscar el asistente.",
            ),
            TextInput(
                id="policy_id",
                label="Filtro de póliza (opcional)",
                initial=cl.user_session.get(POLICY_ID_SESSION_KEY) or "",
                placeholder="Ejemplo: POL320190074",
                description="Déjalo vacío para consultar todas las pólizas.",
            ),
        ]
    ).send()


@cl.set_starters
async def set_starters() -> list[cl.Starter]:
    return [
        cl.Starter(
            label="Revisar exclusiones",
            message="¿Cuáles son las principales exclusiones de las pólizas?",
            icon="FileSearch",
        ),
        cl.Starter(
            label="Comparar con noticias",
            message=(
                "Compara la cobertura catastrófica de las pólizas con novedades "
                "recientes del sector asegurador en Ecuador."
            ),
            icon="Newspaper",
        ),
        cl.Starter(
            label="Crear borrador",
            message=(
                "/draft POL320190074 | Crea un borrador breve de cobertura para "
                "demostración y revisión humana."
            ),
            icon="FilePenLine",
        ),
        cl.Starter(
            label="Ver estado",
            message="/ready",
            icon="Activity",
        ),
    ]


@cl.on_chat_start
async def on_chat_start() -> None:
    readiness = await check_readiness()
    cl.user_session.set(POLICY_ID_SESSION_KEY, None)
    cl.user_session.set(MODE_SESSION_KEY, "auto")
    await _send_settings()

    await cl.Message(
        content=(
            "## Seguros AI\n\n"
            f"{_format_readiness(readiness)}\n\n"
            "Consulta coberturas, exclusiones y condiciones, compara información "
            "actual o crea un borrador para revisión humana. Selecciona un modo "
            "con los botones o abre la configuración del chat.\n\n"
            "Escribe `/help` para ver todos los comandos."
        ),
        actions=_mode_actions(),
    ).send()


@cl.on_settings_update
async def on_settings_update(settings: dict[str, Any]) -> None:
    mode = str(settings.get("mode", "auto"))
    if mode not in VALID_MODES:
        mode = "auto"
    policy_id = str(settings.get("policy_id", "")).strip() or None
    cl.user_session.set(MODE_SESSION_KEY, mode)
    cl.user_session.set(POLICY_ID_SESSION_KEY, policy_id)
    scope = f"póliza `{policy_id}`" if policy_id else "todas las pólizas"
    await cl.Message(
        content=f"Configuración actualizada: {MODE_LABELS[mode]} · {scope}."
    ).send()


@cl.action_callback("set_mode")
async def set_mode_action(action: cl.Action) -> None:
    mode = str(action.payload.get("mode", "auto"))
    if mode not in VALID_MODES:
        return
    cl.user_session.set(MODE_SESSION_KEY, mode)
    await _send_settings()
    await cl.Message(content=f"Modo activo: {MODE_LABELS[mode]}").send()


async def _show_readiness() -> None:
    readiness = await check_readiness()
    await cl.Message(content=f"### Estado del sistema\n\n{_format_readiness(readiness)}").send()


async def _show_config() -> None:
    config = await fetch_config()
    if config is None:
        await cl.Message(content="🔴 No fue posible consultar `/config`.").send()
        return
    threshold = config.score_threshold if config.score_threshold is not None else "Desactivado"
    configured = "Sí" if config.openai_configured else "No"
    await cl.Message(
        content=(
            "### Configuración activa\n\n"
            "| Componente | Valor |\n|---|---|\n"
            f"| Generación | `{config.llm_model}` |\n"
            f"| Router | `{config.router_model}` |\n"
            f"| Búsqueda web | `{config.web_model}` |\n"
            f"| Embeddings | `{config.embedding_model}` |\n"
            f"| Vector store | {config.vector_store} |\n"
            f"| Colección | `{config.collection}` |\n"
            f"| Top-k | {config.top_k} |\n"
            f"| Umbral | {threshold} |\n"
            f"| OpenAI configurado | {configured} |"
        )
    ).send()


async def _stream_text(message: cl.Message, text: str, chunk_size: int = 24) -> None:
    first = True
    for start in range(0, len(text), chunk_size):
        chunk = text[start : start + chunk_size]
        await message.stream_token(chunk, is_sequence=first)
        first = False
        if STREAM_RENDER_DELAY_SECONDS > 0:
            await asyncio.sleep(STREAM_RENDER_DELAY_SECONDS)


async def _generate_draft(policy_ids: list[str], instructions: str) -> None:
    message = cl.Message(content="✍️ Preparando evidencia para el borrador…")
    await message.send()
    try:
        result = await generate_policy_draft(instructions, policy_ids)
    except (ApiTimeoutError, ApiUnavailableError, ApiResponseError) as exc:
        message.content = f"🔴 No fue posible generar el borrador: {exc}"
        await message.update()
        return

    await _stream_text(message, result.draft)
    await message.stream_token(
        f"\n\n> ⚠️ {result.disclaimer}"
        f"{_format_response_context(result.metadata, 'draft', None)}"
        f"{_format_sources(result.sources)}"
    )
    await message.update()


async def _answer_with_stream(question: str, policy_id: str | None, mode: str) -> None:
    message = cl.Message(content="⏳ Conectando con el motor RAG…")
    await message.send()
    answer_started = False
    completed = False
    sources: list[str] = []
    metadata: dict[str, Any] = {}

    try:
        async for event in stream_question(question, policy_id, mode):
            if event.event == "status" and not answer_started:
                message.content = f"⏳ {event.data.get('message', 'Procesando…')}"
                await message.update()
            elif event.event == "token":
                token = str(event.data.get("text", ""))
                if token:
                    await message.stream_token(token, is_sequence=not answer_started)
                    answer_started = True
                    if STREAM_RENDER_DELAY_SECONDS > 0:
                        await asyncio.sleep(STREAM_RENDER_DELAY_SECONDS)
            elif event.event == "complete":
                sources = list(event.data.get("sources", []))
                metadata = dict(event.data.get("metadata", {}))
                completed = True
            elif event.event == "error":
                raise ApiResponseError(
                    int(event.data.get("status_code", 500)),
                    str(event.data.get("detail", "Error desconocido")),
                )
    except ApiTimeoutError:
        message.content = "🟠 La consulta tardó demasiado. Inténtalo nuevamente."
        await message.update()
        return
    except ApiUnavailableError:
        message.content = (
            "🔴 No puedo conectar con el backend. Confirma que Docker y la API estén activos."
        )
        await message.update()
        return
    except ApiResponseError as exc:
        message.content = f"🔴 El backend devolvió un error: {exc.detail}"
        await message.update()
        return

    if not completed:
        message.content = "🔴 La conexión terminó antes de completar la respuesta."
        await message.update()
        return
    if not answer_started:
        await message.stream_token("No se recibió contenido para esta consulta.", is_sequence=True)

    await message.stream_token(
        _format_response_context(metadata, mode, policy_id) + _format_sources(sources)
    )
    await message.update()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    normalized = message.content.strip()
    lowered = normalized.lower()

    if lowered == READY_COMMAND:
        await _show_readiness()
        return
    if lowered == CONFIG_COMMAND:
        await _show_config()
        return
    if lowered == HELP_COMMAND:
        await cl.Message(content=_help_text(), actions=_mode_actions()).send()
        return

    policy_argument = _parse_policy_command(normalized)
    if policy_argument is not None:
        stored_value = policy_argument or None
        cl.user_session.set(POLICY_ID_SESSION_KEY, stored_value)
        await _send_settings()
        confirmation = (
            f"Filtro activo: póliza `{stored_value}`."
            if stored_value
            else "Filtro eliminado: se consultarán todas las pólizas."
        )
        await cl.Message(content=confirmation).send()
        return

    mode_argument = _parse_mode_command(normalized)
    if mode_argument is not None:
        if mode_argument not in VALID_MODES:
            await cl.Message(
                content="Modo inválido. Usa: `auto`, `policies`, `web` o `combined`."
            ).send()
            return
        cl.user_session.set(MODE_SESSION_KEY, mode_argument)
        await _send_settings()
        await cl.Message(content=f"Modo activo: {MODE_LABELS[mode_argument]}").send()
        return

    draft_argument = _parse_draft_command(normalized)
    if draft_argument is not None:
        policy_ids, instructions = draft_argument
        if not 1 <= len(policy_ids) <= 3 or len(instructions) < 10:
            await cl.Message(
                content=(
                    "Usa `/draft POL1,POL2 | instrucciones` con una a tres pólizas "
                    "y al menos 10 caracteres de instrucciones."
                )
            ).send()
            return
        await _generate_draft(policy_ids, instructions)
        return

    if not normalized:
        await cl.Message(content="Escribe una pregunta para continuar.").send()
        return

    policy_id = cl.user_session.get(POLICY_ID_SESSION_KEY) or _extract_policy_id(normalized)
    mode = cl.user_session.get(MODE_SESSION_KEY) or "auto"
    await _answer_with_stream(normalized, policy_id, mode)
