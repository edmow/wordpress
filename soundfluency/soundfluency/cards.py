"""Renderiza os cartões (frames estáticos) do vídeo com Pillow."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _hex(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_text(draw, text, font_path, max_width, start_size, min_size=36):
    """Diminui a fonte até o texto caber em no máximo 3 linhas."""
    size = start_size
    while size > min_size:
        font = _font(font_path, size)
        lines = _wrap(draw, text, font, max_width)
        if len(lines) <= 3:
            return font, lines
        size -= 6
    font = _font(font_path, min_size)
    return font, _wrap(draw, text, font, max_width)


def render_phrase_card(
    background: Image.Image,
    cfg: dict,
    lesson: dict,
    phrase: dict,
    index: int,
    total: int,
    out_png: Path,
) -> None:
    style = cfg["style"]
    img = background.copy().convert("RGBA")
    w, h = img.size
    draw = ImageDraw.Draw(img)

    accent = _hex(style["accent_color"])
    text_color = _hex(style["text_color"])
    trans_color = _hex(style["translation_color"])

    margin = int(w * 0.08)
    max_text_width = w - 2 * margin

    header_font = _font(style["font_regular"], int(h * 0.030))
    draw.text((margin, int(h * 0.055)), lesson["title"], font=header_font, fill=trans_color)
    if style.get("show_phrase_counter", True):
        counter = f"{index}/{total}"
        cw = draw.textlength(counter, font=header_font)
        draw.text((w - margin - cw, int(h * 0.055)), counter, font=header_font, fill=trans_color)
    # linha de destaque sob o cabeçalho
    draw.rectangle([margin, int(h * 0.105), margin + int(w * 0.06), int(h * 0.105) + 6], fill=accent)

    translation = phrase.get("pt") if style.get("show_translation", True) else None

    en_font, en_lines = _fit_text(draw, phrase["en"], style["font_bold"], max_text_width, int(h * 0.075))
    line_h_en = int(en_font.size * 1.3)
    block_h = len(en_lines) * line_h_en
    pt_font, pt_lines, line_h_pt = None, [], 0
    if translation:
        pt_font, pt_lines = _fit_text(draw, translation, style["font_regular"], max_text_width, int(h * 0.042))
        line_h_pt = int(pt_font.size * 1.35)
        block_h += int(h * 0.045) + len(pt_lines) * line_h_pt

    # painel translúcido atrás do texto para legibilidade em qualquer fundo
    panel_pad = int(h * 0.06)
    panel_top = (h - block_h) // 2 - panel_pad
    panel_bottom = (h + block_h) // 2 + panel_pad
    panel = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(panel).rounded_rectangle(
        [margin - panel_pad, panel_top, w - margin + panel_pad, panel_bottom],
        radius=28,
        fill=(8, 10, 18, int(style.get("panel_opacity", 140))),
    )
    img = Image.alpha_composite(img, panel)
    draw = ImageDraw.Draw(img)

    y = (h - block_h) // 2
    for line in en_lines:
        lw = draw.textlength(line, font=en_font)
        draw.text(((w - lw) / 2, y), line, font=en_font, fill=text_color)
        y += line_h_en
    if pt_lines:
        y += int(h * 0.045)
        for line in pt_lines:
            lw = draw.textlength(line, font=pt_font)
            draw.text(((w - lw) / 2, y), line, font=pt_font, fill=trans_color)
            y += line_h_pt

    hint = style.get("repeat_hint", "")
    if hint:
        hint_font = _font(style["font_regular"], int(h * 0.026))
        hw = draw.textlength(hint, font=hint_font)
        draw.text(((w - hw) / 2, int(h * 0.88)), hint, font=hint_font, fill=accent)

    img.convert("RGB").save(out_png)


def render_title_card(background: Image.Image, cfg: dict, lesson: dict, out_png: Path) -> None:
    style = cfg["style"]
    img = background.copy().convert("RGBA")
    w, h = img.size
    draw = ImageDraw.Draw(img)

    accent = _hex(style["accent_color"])
    text_color = _hex(style["text_color"])
    trans_color = _hex(style["translation_color"])

    brand_font = _font(style["font_bold"], int(h * 0.038))
    brand = "SoundFluency"
    bw = draw.textlength(brand, font=brand_font)
    draw.text(((w - bw) / 2, int(h * 0.16)), brand, font=brand_font, fill=accent)

    title_font, title_lines = _fit_text(draw, lesson["title"], style["font_bold"], int(w * 0.84), int(h * 0.095))
    y = int(h * 0.40)
    for line in title_lines:
        lw = draw.textlength(line, font=title_font)
        draw.text(((w - lw) / 2, y), line, font=title_font, fill=text_color)
        y += int(title_font.size * 1.25)

    subtitle = lesson.get("subtitle") or ""
    level = lesson.get("level")
    if level:
        subtitle = f"{subtitle}  •  Nível {level}" if subtitle else f"Nível {level}"
    if subtitle:
        sub_font = _font(style["font_regular"], int(h * 0.036))
        sw = draw.textlength(subtitle, font=sub_font)
        draw.text(((w - sw) / 2, y + int(h * 0.03)), subtitle, font=sub_font, fill=trans_color)

    img.convert("RGB").save(out_png)
