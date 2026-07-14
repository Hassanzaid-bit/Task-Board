"""In-memory WebSocket connection manager, keyed by project (board) id.

Single-process by design — At >1 worker this is
where a Redis pub/sub relay would slot in.
"""

from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._by_project: dict[int, list[WebSocket]] = defaultdict(list)

    async def connect(self, project_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self._by_project[project_id].append(ws)

    def disconnect(self, project_id: int, ws: WebSocket) -> None:
        if ws in self._by_project.get(project_id, []):
            self._by_project[project_id].remove(ws)

    async def broadcast(self, project_id: int, message: dict) -> None:
        """Send to every socket on the board; prune any that are dead.

        Failures are swallowed on purpose: a dropped client must never
        block or roll back the HTTP response that triggered the broadcast.
        """
        for ws in list(self._by_project.get(project_id, [])):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(project_id, ws)


manager = ConnectionManager()
