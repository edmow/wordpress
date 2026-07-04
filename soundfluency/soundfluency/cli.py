"""CLI do SoundFluency.

Uso:
  python -m soundfluency build lessons/001-daily-routines.json
  python -m soundfluency build lessons/*.json --engine kokoro
  python -m soundfluency doctor
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from .config import PROJECT_ROOT, load_config


def cmd_build(args) -> None:
    from .tts import make_engine
    from .video import build_lesson

    overrides = {}
    if args.vertical:
        overrides["video"] = {"width": 1080, "height": 1920}
    cfg = load_config(overrides=overrides)
    engine = make_engine(cfg, args.engine)
    out_dir = Path(args.out) if args.out else PROJECT_ROOT / cfg["output"]["dir"]

    for lesson in args.lessons:
        lesson_path = Path(lesson)
        if not lesson_path.exists():
            sys.exit(f"Lição não encontrada: {lesson_path}")
        with tempfile.TemporaryDirectory(prefix="soundfluency-") as tmp:
            build_lesson(lesson_path, cfg, engine, out_dir, Path(tmp))


def cmd_doctor(_args) -> None:
    ok = True

    def check(label: str, passed: bool, hint: str = "") -> None:
        nonlocal ok
        mark = "✔" if passed else "✘"
        print(f" {mark} {label}" + (f" — {hint}" if hint and not passed else ""))
        ok = ok and passed

    check("ffmpeg", shutil.which("ffmpeg") is not None, "instale com: apt install ffmpeg")
    try:
        import kokoro_onnx  # noqa: F401
        check("kokoro-onnx", True)
    except ImportError:
        check("kokoro-onnx", False, "pip install -r requirements.txt")
    for mod in ("soundfile", "PIL", "yaml", "numpy"):
        try:
            __import__(mod)
            check(mod, True)
        except ImportError:
            check(mod, False, "pip install -r requirements.txt")

    from .tts import MODEL_DIR
    model_ok = (MODEL_DIR / "kokoro-v1.0.onnx").exists() and (MODEL_DIR / "voices-v1.0.bin").exists()
    check(
        "modelo Kokoro baixado",
        model_ok,
        "será baixado automaticamente no primeiro build (~310 MB + 27 MB)",
    )

    cfg = load_config()
    font_ok = Path(cfg["style"]["font_bold"]).exists() and Path(cfg["style"]["font_regular"]).exists()
    check("fontes configuradas", font_ok, "ajuste style.font_* no config.yaml")

    sys.exit(0 if ok else 1)


def main() -> None:
    parser = argparse.ArgumentParser(prog="soundfluency", description="Produção de vídeos para prática de inglês")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="Gera o(s) vídeo(s) de uma ou mais lições")
    p_build.add_argument("lessons", nargs="+", help="Arquivo(s) JSON de lição")
    p_build.add_argument("--engine", choices=["kokoro", "elevenlabs", "espeak"], default=None,
                         help="Sobrescreve o engine de TTS do config.yaml")
    p_build.add_argument("--out", default=None, help="Diretório de saída (padrão: output/)")
    p_build.add_argument("--vertical", action="store_true", help="Formato 1080x1920 (Shorts/Reels)")
    p_build.set_defaults(func=cmd_build)

    p_doctor = sub.add_parser("doctor", help="Verifica dependências e ambiente")
    p_doctor.set_defaults(func=cmd_doctor)

    args = parser.parse_args()
    args.func(args)
