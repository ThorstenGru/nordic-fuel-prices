"""Elevator music for the Facebook videos, made from nothing: no sample, no recording, no licence question.

A slow lounge loop (82 BPM, soft electric-piano chords Cmaj9 - Am9 - Dm9 - G13, a walking-style bass, a quiet brush on the off-beats), synthesised with
the standard library only and mixed under a video with ffmpeg. Deterministic: the same call gives the same bytes, so it can be tested.

    python tools/fb_music.py OUT.wav [SECONDS]
"""
import math
import random
import struct
import subprocess
import wave
from pathlib import Path

RATE = 44100
BPM = 82
BEAT = 60.0 / BPM
# chord = (bass MIDI note, chord tones MIDI): C maj9, A min9, D min9, G13
CHORDS = [(36, [52, 55, 59, 62, 64]), (33, [48, 52, 55, 59, 62]), (38, [53, 57, 60, 64, 67]), (31, [47, 53, 55, 59, 64])]


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _note(buf, start, dur, freq, amp, kind="ep"):
    """Add one note (electric-piano-ish: a sine plus a bell-like 2nd and 4th partial, quick attack, exponential decay) into buf at `start` seconds."""
    i0, n = int(start * RATE), int(dur * RATE)
    for k in range(n):
        i = i0 + k
        if i >= len(buf):
            break
        t = k / RATE
        attack = min(1.0, t / 0.01)
        env = attack * math.exp(-t * (1.6 if kind == "ep" else 2.2))
        if kind == "ep":
            v = math.sin(2 * math.pi * freq * t) + 0.35 * math.sin(2 * math.pi * freq * 2 * t) * math.exp(-t * 4) + 0.12 * math.sin(2 * math.pi * freq * 4 * t) * math.exp(-t * 9)
        else:                                            # bass: a round sine with a touch of the 2nd partial
            v = math.sin(2 * math.pi * freq * t) + 0.25 * math.sin(2 * math.pi * freq * 2 * t)
        buf[i] += amp * env * v


def render(seconds: float = 24.0) -> list:
    """Mono samples in [-1, 1], `seconds` long, with a short fade in and a 1.5 s fade out."""
    rnd = random.Random(7)
    n = int(seconds * RATE)
    buf = [0.0] * n
    bar = 4 * BEAT
    t, b = 0.0, 0
    while t < seconds:
        bass, tones = CHORDS[b % len(CHORDS)]
        _note(buf, t, BEAT * 1.9, hz(bass), 0.34, "bass")
        _note(buf, t + 2 * BEAT, BEAT * 1.9, hz(bass + 7), 0.26, "bass")
        for j, m in enumerate(tones):                    # a gentle upward roll of the chord, then a soft second hit on beat 3
            _note(buf, t + j * 0.045, bar * 0.9, hz(m), 0.085)
            _note(buf, t + 2.5 * BEAT + j * 0.03, BEAT * 1.4, hz(m), 0.05)
        for q in range(4):                               # brush: a few ms of filtered noise on the off-beats
            s0 = int((t + q * BEAT + BEAT / 2) * RATE)
            last = 0.0
            for k in range(int(0.05 * RATE)):
                if s0 + k >= n:
                    break
                x = rnd.uniform(-1, 1)
                last = 0.6 * last + 0.4 * x
                buf[s0 + k] += 0.05 * last * math.exp(-k / (0.012 * RATE))
        t += bar
        b += 1
    peak = max(1e-9, max(abs(x) for x in buf))
    g = 0.5 / peak                                       # leave plenty of headroom: it sits UNDER the pictures, about -6 dBFS peak
    fin, fout = int(0.4 * RATE), int(1.5 * RATE)
    for i in range(n):
        f = min(1.0, i / fin, (n - i) / fout)
        buf[i] *= g * max(0.0, f)
    return buf


def write_wav(path: Path, samples: list) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, x)) * 32767)) for x in samples))


def add_music(video: Path, seconds: float, tmp_dir: Path = None) -> bool:
    """Replace `video` (silent) with a copy that has the music under it. False (and the original stays) if anything fails, so a video is never lost for music."""
    tmp_dir = tmp_dir or video.parent
    wav, out = tmp_dir / "music.wav", tmp_dir / (video.stem + "_m.mp4")
    try:
        write_wav(wav, render(seconds + 0.5))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(wav), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", "-shortest", "-movflags", "+faststart", str(out)], check=True)
        out.replace(video)
        return True
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"fb_music: no music this time ({type(e).__name__}); the silent video is kept")
        return False
    finally:
        wav.unlink(missing_ok=True)
        out.unlink(missing_ok=True)


if __name__ == "__main__":
    import sys
    write_wav(Path(sys.argv[1]), render(float(sys.argv[2]) if len(sys.argv) > 2 else 24.0))
