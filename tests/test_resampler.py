"""Tests for StreamingResampler: chunked output must be bit-identical to
one-shot processing (proves chunk boundaries introduce no discontinuities),
and resampling must not introduce audible aliasing."""

import os

import numpy as np
import pytest
from scipy import signal

# audiocall.main builds a TwilioClient at import time, which raises on empty
# credentials — provide dummies so the tests run without a configured .env.
os.environ.setdefault("TWILIO_ACCOUNT_SID", "ACtest")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test")

from audiocall.main import StreamingResampler  # noqa: E402

RATE_PAIRS = [(8000, 16000), (24000, 8000)]


def _chirp_pcm16(rate: int, seconds: float = 2.0) -> bytes:
    t = np.arange(int(rate * seconds)) / rate
    sweep = signal.chirp(t, f0=100, f1=3800, t1=seconds) * 0.8 * 32767
    return sweep.astype(np.int16).tobytes()


@pytest.mark.parametrize("in_rate,out_rate", RATE_PAIRS)
def test_chunked_matches_one_shot(in_rate: int, out_rate: int) -> None:
    audio = _chirp_pcm16(in_rate)

    one_shot = StreamingResampler(in_rate, out_rate).process(audio)

    rng = np.random.default_rng(42)
    streamer = StreamingResampler(in_rate, out_rate)
    chunked = bytearray()
    pos = 0
    while pos < len(audio):
        # Random sizes including odd byte counts, 1-byte, and empty chunks
        size = int(rng.integers(0, 700))
        chunked += streamer.process(audio[pos : pos + size])
        pos += size

    assert bytes(chunked) == one_shot


@pytest.mark.parametrize("in_rate,out_rate", RATE_PAIRS)
def test_no_aliasing_on_pure_tone(in_rate: int, out_rate: int) -> None:
    rate = in_rate
    t = np.arange(rate * 2) / rate
    tone = (np.sin(2 * np.pi * 1000 * t) * 0.5 * 32767).astype(np.int16)

    out = StreamingResampler(in_rate, out_rate).process(tone.tobytes())
    y = np.frombuffer(out, dtype=np.int16).astype(np.float64)

    spectrum = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    freqs = np.fft.rfftfreq(len(y), 1 / out_rate)
    fundamental = spectrum[np.abs(freqs - 1000) < 20].max()
    spurious = spectrum[np.abs(freqs - 1000) > 100].max()

    assert 20 * np.log10(fundamental / spurious) >= 55


@pytest.mark.parametrize("in_rate,out_rate", RATE_PAIRS)
def test_reset_clears_state(in_rate: int, out_rate: int) -> None:
    audio = _chirp_pcm16(in_rate, seconds=0.5)
    fresh = StreamingResampler(in_rate, out_rate).process(audio)

    reused = StreamingResampler(in_rate, out_rate)
    reused.process(audio[: len(audio) // 2 + 1])  # odd split leaves a carry byte
    reused.reset()
    assert reused.process(audio) == fresh
