from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..realtime import manager
from ..security import decode_access_token

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/boards/{project_id}")
async def board_updates(ws: WebSocket, project_id: int, token: str = "") -> None:
    """Push-only channel: clients receive invalidation signals for one board.

    Auth is via ?token= because the browser WebSocket API can't set an
    Authorization header. 4401 mirrors HTTP 401.
    """
    if decode_access_token(token) is None:
        await ws.close(code=4401, reason="Invalid or missing token")
        return

    await manager.connect(project_id, ws)
    try:
        while True:
            # Nothing meaningful arrives client->server yet; reading keeps the
            # connection alive and lets us notice disconnects promptly.
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(project_id, ws)
