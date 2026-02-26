"""Command API routes — POST /api/v1/command."""

from fastapi import APIRouter, HTTPException

from app.schemas.command import CommandRequest, CommandResource
from app.services import command_service

router = APIRouter(prefix="/api/v1/command", tags=["Commands"])


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
