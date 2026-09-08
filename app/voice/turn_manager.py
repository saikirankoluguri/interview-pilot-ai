"""Small voice state machine; overlapping input is dropped during processing/playback."""

from enum import StrEnum

from app.utils.errors import InvalidSessionState


class TurnState(StrEnum):
    WAITING = "Waiting"
    LISTENING = "Listening"
    PROCESSING = "Processing"
    SPEAKING = "Interviewer speaking"


class TurnManager:
    def __init__(self) -> None:
        self.state = TurnState.WAITING

    def begin_processing(self) -> None:
        if self.state not in {TurnState.WAITING, TurnState.LISTENING}:
            raise InvalidSessionState("A voice turn is already being processed or played.")
        self.state = TurnState.PROCESSING

    def begin_speaking(self) -> None:
        if self.state != TurnState.PROCESSING:
            raise InvalidSessionState("Playback requires a processed turn.")
        self.state = TurnState.SPEAKING

    def playback_finished(self, *, ended: bool = False) -> None:
        if self.state == TurnState.SPEAKING:
            self.state = TurnState.WAITING if ended else TurnState.LISTENING

    def recover(self, *, active: bool) -> None:
        self.state = TurnState.LISTENING if active else TurnState.WAITING

    def stop(self) -> None:
        self.state = TurnState.WAITING
