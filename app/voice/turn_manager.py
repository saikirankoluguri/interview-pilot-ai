"""Validated realtime voice state machine independent of UI and transport."""

from enum import StrEnum

from app.utils.errors import InvalidSessionState


class TurnState(StrEnum):
    IDLE = "Idle"
    WAITING = "Idle"  # Phase 1 compatibility alias.
    PREPARING = "Preparing interview..."
    INTERVIEWER_SPEAKING = "Interviewer speaking"
    SPEAKING = "Interviewer speaking"  # Phase 1 compatibility alias.
    LISTENING = "Listening"
    CANDIDATE_SPEAKING = "You're speaking"
    PROCESSING = "Processing response"
    ENDING = "Wrapping up"
    COMPLETED = "Completed"
    ERROR = "Error"


class ConnectionState(StrEnum):
    CONNECTING = "Connecting"
    CONNECTED = "Connected"
    RECONNECTING = "Reconnecting"
    DISCONNECTED = "Disconnected"


class TurnManager:
    def __init__(self) -> None:
        self.state = TurnState.IDLE
        self.history = [self.state]

    def _move(self, state: TurnState, allowed: set[TurnState]) -> None:
        if self.state not in allowed:
            raise InvalidSessionState(f"Cannot move voice state from {self.state} to {state}.")
        self.state = state
        self.history.append(state)

    def begin_preparing(self) -> None:
        self._move(TurnState.PREPARING, {TurnState.IDLE})

    def begin_processing(self) -> None:
        self._move(
            TurnState.PROCESSING,
            {
                TurnState.IDLE,
                TurnState.PREPARING,
                TurnState.LISTENING,
                TurnState.CANDIDATE_SPEAKING,
            },
        )

    def begin_speaking(self) -> None:
        self._move(
            TurnState.INTERVIEWER_SPEAKING,
            {TurnState.PREPARING, TurnState.PROCESSING, TurnState.ENDING},
        )

    def begin_listening(self) -> None:
        self._move(
            TurnState.LISTENING,
            {TurnState.INTERVIEWER_SPEAKING, TurnState.IDLE},
        )

    def speech_started(self) -> None:
        self._move(TurnState.CANDIDATE_SPEAKING, {TurnState.LISTENING})

    def begin_ending(self) -> None:
        if self.state == TurnState.ENDING:
            return
        self._move(
            TurnState.ENDING,
            {
                TurnState.IDLE,
                TurnState.PREPARING,
                TurnState.INTERVIEWER_SPEAKING,
                TurnState.LISTENING,
                TurnState.CANDIDATE_SPEAKING,
                TurnState.PROCESSING,
                TurnState.ERROR,
            },
        )

    def playback_finished(self, *, ended: bool = False) -> None:
        if self.state != TurnState.INTERVIEWER_SPEAKING:
            return
        self.state = TurnState.ENDING if ended else TurnState.LISTENING
        self.history.append(self.state)

    def complete(self) -> None:
        self._move(
            TurnState.COMPLETED,
            {TurnState.ENDING, TurnState.INTERVIEWER_SPEAKING},
        )

    def fail(self) -> None:
        if self.state != TurnState.ERROR:
            self.state = TurnState.ERROR
            self.history.append(self.state)

    def recover(self, *, active: bool) -> None:
        self.state = TurnState.LISTENING if active else TurnState.IDLE
        self.history.append(self.state)

    def stop(self) -> None:
        self.state = TurnState.IDLE
        self.history.append(self.state)
