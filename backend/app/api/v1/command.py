"""Command API routes — POST /api/v1/command."""

import logging

from fastapi import APIRouter, HTTPException

from app.schemas.command import CommandRequest, CommandResource
from app.services import command_service
from app.services.command_service import register_command

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/command", tags=["Commands"])

# ---------------------------------------------------------------------------
# ScanLibrary command
# ---------------------------------------------------------------------------

_scan_running = False


async def _handle_scan_library() -> str | None:
    """Scan all root folders for existing magazine files."""
    global _scan_running
    if _scan_running:
        raise ValueError("A library scan is already in progress")
    _scan_running = True

    try:
        from app.api.v1.websocket import manager as ws_manager
        from app.database import async_session_factory
        from app.dependencies import get_config
        from app.services.scan_service import scan_library

        if async_session_factory is None:
            return "Database not initialized"

        config = get_config()

        async with async_session_factory() as db:

            async def on_progress(progress):
                await ws_manager.broadcast("scan:progress", progress.to_dict())

            progress = await scan_library(db, config, on_progress=on_progress)
            await db.commit()

            await ws_manager.broadcast("scan:completed", progress.to_dict())
            await ws_manager.broadcast("library:updated", {})

            return (
                f"Scan complete: {progress.new_files} files registered, "
                f"{progress.new_magazines} new magazines, "
                f"{progress.new_issues} new issues, "
                f"{progress.errors} errors"
            )
    finally:
        _scan_running = False


register_command("ScanLibrary", _handle_scan_library)


@router.get("", response_model=list[CommandResource])
async def list_commands() -> list[CommandResource]:
    """List all commands."""
    return command_service.list_commands()


@router.post("", response_model=CommandResource, status_code=201)
async def execute_command(request: CommandRequest) -> CommandResource:
    """Execute an async command."""
    try:
        return await command_service.execute_command(
            name=request.name,
            body=request.body,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{command_id}", response_model=CommandResource)
async def get_command(command_id: int) -> CommandResource:
    """Get command status by ID."""
    command = command_service.get_command(command_id)
    if not command:
        raise HTTPException(status_code=404, detail="Command not found")
    return command
