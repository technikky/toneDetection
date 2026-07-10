"""Stage 14: real-time WebSocket layer for teacher-led live practice
sessions. A teacher "sends" an exercise, which is broadcast to every
connected student; each student then streams their live pitch/level back
so the teacher can watch the whole class practice in real time, not just
review takes after the fact.

In-memory, single-process state -- appropriate for this app's single
teacher / single classroom / single machine deployment model.
"""
import logging
from typing import Optional

from fastapi import WebSocket

log = logging.getLogger("sight_singing.live")


class LiveSessionManager:
    def __init__(self):
        self.students: dict[WebSocket, dict] = {}
        self.teachers: set[WebSocket] = set()
        self.current_assignment: Optional[dict] = None

    # -- students --------------------------------------------------------

    async def student_join(self, ws: WebSocket, name: str) -> None:
        self.students[ws] = {"name": name, "status": "idle", "hz": None, "midi": None, "level": 0.0}
        await self._broadcast_roster()
        if self.current_assignment:
            await self._send(ws, {"type": "assignment", **self.current_assignment})

    async def student_leave(self, ws: WebSocket) -> None:
        if ws in self.students:
            del self.students[ws]
            await self._broadcast_roster()

    async def student_status(self, ws: WebSocket, status: str) -> None:
        if ws in self.students:
            self.students[ws]["status"] = status
            await self._broadcast_roster()

    async def mark_submitted_by_name(self, student_name: str) -> None:
        """Called from the HTTP /api/submit handler (no WebSocket in scope
        there) so the teacher's live roster reflects a completed take."""
        changed = False
        for info in self.students.values():
            if info["name"].strip().lower() == student_name.strip().lower():
                info["status"] = "submitted"
                changed = True
        if changed:
            await self._broadcast_roster()

    async def student_pitch(self, ws: WebSocket, hz, midi, level) -> None:
        info = self.students.get(ws)
        if info is None:
            return
        info["hz"], info["midi"], info["level"] = hz, midi, level
        await self._broadcast_to_teachers({
            "type": "pitch_update",
            "student_name": info["name"],
            "hz": hz,
            "midi": midi,
            "level": level,
        })

    # -- teachers ----------------------------------------------------------

    async def teacher_join(self, ws: WebSocket) -> None:
        self.teachers.add(ws)
        await self._send(ws, self._roster_message())

    async def teacher_leave(self, ws: WebSocket) -> None:
        self.teachers.discard(ws)

    async def teacher_assign(self, song_id: str, difficulty: Optional[str]) -> None:
        self.current_assignment = {"song_id": song_id, "difficulty": difficulty}
        message = {"type": "assignment", "song_id": song_id, "difficulty": difficulty}
        for ws in list(self.students.keys()):
            await self._send(ws, message)

    # -- internals -----------------------------------------------------

    def _roster_message(self) -> dict:
        return {
            "type": "roster",
            "students": [
                {
                    "name": info["name"],
                    "status": info["status"],
                    "hz": info["hz"],
                    "midi": info["midi"],
                    "level": info["level"],
                }
                for info in self.students.values()
            ],
        }

    async def _broadcast_roster(self) -> None:
        await self._broadcast_to_teachers(self._roster_message())

    async def _broadcast_to_teachers(self, message: dict) -> None:
        dead = []
        for ws in self.teachers:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.teachers.discard(ws)

    async def _send(self, ws: WebSocket, message: dict) -> None:
        try:
            await ws.send_json(message)
        except Exception:
            log.debug("Dropped message to a closed live-session socket.")


manager = LiveSessionManager()
