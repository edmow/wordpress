"""Fundos dos cartões.

Modo `auto`: se houver imagens em backgrounds/, usa uma por lição (com
escurecimento e desfoque para o texto ficar legível). Sem imagens, gera um
gradiente procedural bonito — o vídeo nunca fica bloqueado por falta de asset.

Dica: imagens 1920x1080+ da Pexels/Unsplash (licença livre) funcionam bem.
Coloque na pasta backgrounds/ e pronto.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

# Paletas (escuro -> claro) usadas nos gradientes procedurais
PALETTES = [
    ((16, 24, 48), (79, 142, 247)),    # azul noite -> azul
    ((24, 16, 48), (167, 112, 239)),   # roxo profundo -> lilás
    ((10, 36, 34), (52, 211, 153)),    # verde escuro -> esmeralda
    ((45, 18, 28), (244, 114, 132)),   # vinho -> rosa
    ((38, 27, 10), (245, 158, 11)),    # marrom -> âmbar
    ((15, 32, 44), (56, 189, 248)),    # petróleo -> ciano
]

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _lesson_seed(lesson_id: str) -> int:
    return int(hashlib.sha256(lesson_id.encode()).hexdigest(), 16)


def _gradient(size: tuple[int, int], seed: int) -> Image.Image:
    w, h = size
    dark, light = PALETTES[seed % len(PALETTES)]
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    # gradiente diagonal
    for y in range(h):
        t = y / h
        color = tuple(int(d + (l - d) * t * 0.65) for d, l in zip(dark, light))
        draw.line([(0, y), (w, y)], fill=color)
    # círculos suaves translúcidos para dar profundidade
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    rng = seed
    for i in range(5):
        rng = (rng * 6364136223846793005 + 1442695040888963407) % (2 ** 63)
        cx = rng % w
        cy = (rng >> 8) % h
        r = int(min(w, h) * (0.15 + 0.25 * ((rng >> 16) % 100) / 100))
        alpha = 14 + (rng >> 24) % 14
        odraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*light, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), overlay.filter(ImageFilter.GaussianBlur(60)))
    return img.convert("RGB")


def _cover_crop(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    w, h = size
    scale = max(w / img.width, h / img.height)
    img = img.resize((math.ceil(img.width * scale), math.ceil(img.height * scale)), Image.LANCZOS)
    left = (img.width - w) // 2
    top = (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def build_background(cfg: dict, lesson: dict, size: tuple[int, int]) -> Image.Image:
    bg_cfg = cfg["backgrounds"]
    mode = bg_cfg["mode"]
    seed = _lesson_seed(str(lesson.get("id", lesson.get("title", "sf"))))

    image_path = None
    if lesson.get("background"):
        image_path = Path(lesson["background"])
        if not image_path.is_absolute():
            from .config import PROJECT_ROOT
            image_path = PROJECT_ROOT / image_path
    elif mode in ("auto", "images"):
        from .config import PROJECT_ROOT
        bg_dir = PROJECT_ROOT / bg_cfg["dir"]
        candidates = sorted(
            p for p in bg_dir.glob("*") if p.suffix.lower() in IMAGE_EXTS
        ) if bg_dir.exists() else []
        if candidates:
            image_path = candidates[seed % len(candidates)]
        elif mode == "images":
            raise SystemExit(
                f"backgrounds.mode=images mas não há imagens em {bg_dir}. "
                "Adicione .jpg/.png lá ou mude para mode: auto."
            )

    if image_path and image_path.exists():
        img = _cover_crop(Image.open(image_path).convert("RGB"), size)
        if bg_cfg.get("blur", 0):
            img = img.filter(ImageFilter.GaussianBlur(bg_cfg["blur"]))
        img = ImageEnhance.Brightness(img).enhance(1 - bg_cfg.get("darken", 0.55))
        return img

    return _gradient(size, seed)
