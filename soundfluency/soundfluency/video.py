"""Montagem do vídeo final com ffmpeg.

Fluxo por lição:
  1. TTS de cada frase (velocidade normal e lenta) -> WAVs
  2. Áudio da frase = padrão de pacing (normal/pausa/lenta/...) concatenado
  3. Cartão PNG por frase + cartão de título
  4. Segmento MP4 por cartão (imagem estática + áudio)
  5. Concatenação de todos os segmentos + loudness normalizado
  6. Legenda .srt sincronizada (opcional)
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soundfile as sf

from . import cards, tts
from .backgrounds import build_background


@dataclass
class Segment:
    png: Path
    wav: Path
    duration: float
    subtitle: str | None = None


@dataclass
class Timeline:
    segments: list[Segment] = field(default_factory=list)

    @property
    def total(self) -> float:
        return sum(s.duration for s in self.segments)


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _phrase_audio(engine, phrase: dict, pacing: dict, tts_cfg: dict, work: Path, idx: int) -> tuple[np.ndarray, float]:
    """Gera o áudio completo de uma frase seguindo o padrão de pacing."""
    normal_wav = work / f"p{idx:03d}_normal.wav"
    slow_wav = work / f"p{idx:03d}_slow.wav"
    dur_normal = engine.synth(phrase["en"], normal_wav, speed=tts_cfg["speed_normal"])
    dur_slow = None

    chunks: list[np.ndarray] = []
    last_dur = dur_normal
    for step in pacing["pattern"]:
        if step == "normal":
            chunks.append(tts.load_wav(normal_wav))
            last_dur = dur_normal
        elif step == "slow":
            if dur_slow is None:
                dur_slow = engine.synth(phrase["en"], slow_wav, speed=tts_cfg["speed_slow"])
            chunks.append(tts.load_wav(slow_wav))
            last_dur = dur_slow
        elif step == "pause":
            chunks.append(tts.silence(last_dur * pacing["pause_factor"]))
        else:
            raise SystemExit(f"Passo de pacing desconhecido: {step}")
    chunks.append(tts.silence(pacing["gap_between_phrases"]))

    audio = np.concatenate(chunks)
    return audio, len(audio) / tts.SAMPLE_RATE


def _make_segment_mp4(seg: Segment, cfg: dict, out_mp4: Path) -> None:
    v = cfg["video"]
    _run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-i", str(seg.png),
        "-i", str(seg.wav),
        "-t", f"{seg.duration:.3f}",
        "-r", str(v["fps"]),
        "-c:v", v["codec"], "-crf", str(v["crf"]), "-preset", "medium",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", v["audio_bitrate"],
        "-shortest",
        str(out_mp4),
    ])


def _srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _write_srt(timeline: Timeline, out_srt: Path) -> None:
    lines, t, n = [], 0.0, 0
    for seg in timeline.segments:
        if seg.subtitle:
            n += 1
            lines += [str(n), f"{_srt_time(t)} --> {_srt_time(t + seg.duration)}", seg.subtitle, ""]
        t += seg.duration
    out_srt.write_text("\n".join(lines), encoding="utf-8")


def build_lesson(lesson_path: Path, cfg: dict, engine, out_dir: Path, work_dir: Path) -> Path:
    lesson = json.loads(lesson_path.read_text(encoding="utf-8"))
    lesson_overrides = lesson.get("config") or {}
    if lesson_overrides:
        from .config import _deep_merge
        cfg = _deep_merge(cfg, lesson_overrides)

    v = cfg["video"]
    size = (v["width"], v["height"])
    pacing = cfg["pacing"]
    work_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    background = build_background(cfg, lesson, size)
    timeline = Timeline()

    # cartão de título
    title_png = work_dir / "title.png"
    title_wav = work_dir / "title.wav"
    cards.render_title_card(background, cfg, lesson, title_png)
    title_secs = float(pacing["title_card_seconds"])
    sf.write(title_wav, tts.silence(title_secs), tts.SAMPLE_RATE)
    timeline.segments.append(Segment(title_png, title_wav, title_secs))

    phrases = lesson["phrases"]
    for i, phrase in enumerate(phrases, start=1):
        print(f"[build] frase {i}/{len(phrases)}: {phrase['en']}")
        png = work_dir / f"p{i:03d}.png"
        cards.render_phrase_card(background, cfg, lesson, phrase, i, len(phrases), png)
        audio, duration = _phrase_audio(engine, phrase, pacing, cfg["tts"], work_dir, i)
        wav = work_dir / f"p{i:03d}_full.wav"
        sf.write(wav, audio, tts.SAMPLE_RATE)
        timeline.segments.append(Segment(png, wav, duration, subtitle=f"{phrase['en']}\n{phrase['pt']}"))

    # segmentos mp4 + concat
    concat_list = work_dir / "concat.txt"
    seg_paths = []
    for i, seg in enumerate(timeline.segments):
        mp4 = work_dir / f"seg{i:03d}.mp4"
        _make_segment_mp4(seg, cfg, mp4)
        seg_paths.append(mp4)
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in seg_paths), encoding="utf-8")

    slug = f"{lesson.get('id', 'lesson')}-{lesson['title'].lower().replace(' ', '-')}"
    final = out_dir / f"{slug}.mp4"
    _run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c:v", "copy",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-c:a", "aac", "-b:a", v["audio_bitrate"],
        str(final),
    ])

    if cfg["output"].get("make_srt", True):
        _write_srt(timeline, final.with_suffix(".srt"))

    print(f"[build] pronto: {final}  ({timeline.total:.1f}s)")
    return final
