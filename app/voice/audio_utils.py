"""Audio normalization at transport/runtime boundaries; no AI dependencies."""

import numpy as np
from numpy.typing import NDArray

from app.schemas.audio import AudioBuffer
from app.utils.errors import AudioProcessingError


def from_array(sample_rate: int, samples: NDArray) -> AudioBuffer:
    values = np.asarray(samples)
    if values.ndim not in {1, 2} or values.size == 0:
        raise AudioProcessingError("Microphone audio is empty or invalid.")
    if np.issubdtype(values.dtype, np.integer):
        values = values.astype(np.float32) / max(abs(np.iinfo(values.dtype).min), 1)
    else:
        values = values.astype(np.float32)
    if values.ndim == 2:
        # Gradio is (samples, channels); FastRTC is (channels, samples).
        values = values.mean(axis=0 if values.shape[0] <= 2 else 1)
    if not np.isfinite(values).all():
        raise AudioProcessingError("Microphone audio contains invalid samples.")
    pcm = (np.clip(values, -1, 1) * 32767).astype("<i2").tobytes()
    return AudioBuffer(pcm=pcm, sample_rate=int(sample_rate))


def as_float32(audio: AudioBuffer, sample_rate: int = 16000) -> NDArray[np.float32]:
    """Linear resampling for the POC; transport normally supplies 16 kHz directly."""
    values = np.frombuffer(audio.pcm, dtype="<i2").astype(np.float32) / 32768
    if audio.sample_rate != sample_rate and values.size:
        count = round(values.size * sample_rate / audio.sample_rate)
        values = np.interp(
            np.arange(count) * audio.sample_rate / sample_rate, np.arange(values.size), values
        ).astype(np.float32)
    return values


def for_transport(audio: AudioBuffer) -> tuple[int, NDArray[np.int16]]:
    return audio.sample_rate, np.frombuffer(audio.pcm, dtype="<i2").copy()
