"""Async command execution framework."""

import asyncio
import logging
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

from app.schemas.command import CommandResource, CommandStatus

logger = logging.getLogger(__name__)

# In-memory command tracking
_commands: dict[int, CommandResource] = {}
_command_counter: int = 0
_command_handlers: dict[str, Callable[..., Coroutine[Any, Any, str | None]]] = {}


def register_command(name: str, handler: Callable[..., Coroutine[Any, Any, str | None]]) -> None:
    """Register a command handler."""
    _command_handlers[name] = handler


async def execute_command(name: str, body: dict | None = None, trigger: str = "manual") -> CommandResource:
    """Execute a command asynchronously."""
    global _command_counter
    _command_counter += 1
    command_id = _command_counter

    if name not in _command_handlers:
        raise ValueError(f"Unknown command: {name}")

    command = CommandResource(
        id=command_id,
        name=name,
        status=CommandStatus.queued,
        started=None,
        ended=None,
        message=None,
        trigger=trigger,
    )
    _commands[command_id] = command

    asyncio.create_task(_run_command(command_id, name, body))
    return command


async def _run_command(command_id: int, name: str, body: dict | None) -> None:
    """Run a command handler and update status."""
    command = _commands[command_id]
    command.status = CommandStatus.started
    command.started = datetime.now(UTC)

    try:
        handler = _command_handlers[name]
        message = await handler(**(body or {}))
        command.status = CommandStatus.completed
        command.message = message
    except Exception as e:
        logger.exception("Command %s failed", name)
        command.status = CommandStatus.failed
        command.message = str(e)
    finally:
        command.ended = datetime.now(UTC)


def get_command(command_id: int) -> CommandResource | None:
    """Get a command by ID."""
    return _commands.get(command_id)


def list_commands() -> list[CommandResource]:
    """List all commands (most recent first)."""
    return sorted(_commands.values(), key=lambda c: c.id, reverse=True)
