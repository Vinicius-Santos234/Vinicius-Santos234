"""Gera o banner do README: mosaico animado em SVG a partir do video.

Loop de 10 s, para sempre: cena 1 (o rapaz, 5 s) -> glitch -> cena 2 (a Capri, 5 s) -> glitch -> ...
Cada cena vai e volta em camera lenta (o cabelo balanca, o brilho da juba pisca), com
alguns caracteres trocando e um brilho de estrela piscando por cima.
O video nao vai para o repositorio (e material do anime e pesa): passe o caminho dele.
Depois, scripts/readme/gerar_visual.py poe a moldura e grava tema/banner.svg.

uso: python scripts/banner/gerar_banner.py VIDEO.webm MOSAICO.svg
"""
import base64
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
import numpy as np
from PIL import Image

import mosaico as st
import video as bf

CELL = st.CELL
W, H = bf.COLS * CELL, bf.ROWS * CELL                       # 800 x 448
CYCLE, HALF = 10.0, 5.0                                     # cena 1 em [0, 5), cena 2 em [5, 10)
S1_FRAMES = list(range(0, bf.CUT1))                         # todos os 37: camera lenta 2x
S1_SLOT = 1 / 15
S2_FRAMES = list(range(bf.CUT1, bf.CUT2, 3))                # 15: so o brilho muda
S2_SLOT = 4.8 / (2 * len(S2_FRAMES) - 1)


# ---------------------------------------------------------------- cores: paleta unica
def palette(colors, k=56):
    allc = np.concatenate([x.reshape(-1, 3) for x in colors]).astype(np.float32)
    rng = np.random.default_rng(0)
    allc = allc[rng.choice(len(allc), min(len(allc), 24000), replace=False)]
    cv2.setRNGSeed(0)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.5)
    _, _, centers = cv2.kmeans(allc, k, None, crit, 4, cv2.KMEANS_PP_CENTERS)
    return centers


def snap(col, centers):
    flat = col.reshape(-1, 3).astype(np.float32)
    d = ((flat[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
    return centers[d.argmin(axis=1)].reshape(col.shape)


# ---------------------------------------------------------------- imagens embutidas
def encode(rgba):
    """Menor entre WebP sem perda e PNG com paleta (este so se sair identico)."""
    im = Image.fromarray(rgba, 'RGBA')
    b = io.BytesIO()
    im.save(b, 'WEBP', lossless=True, quality=100, method=6)
    best = ('image/webp', b.getvalue())
    q = im.quantize(colors=255, method=Image.Quantize.FASTOCTREE)
    if np.array_equal(np.asarray(q.convert('RGBA')), rgba):
        b = io.BytesIO()
        q.save(b, 'PNG', optimize=True)
        if len(b.getvalue()) < len(best[1]):
            best = ('image/png', b.getvalue())
    return best


class Doc:
    def __init__(self):
        self.defs, self.body, self.css, self.bytes = [], [], [], {}
        self.n = 0

    def image(self, ident, rgba, in_defs=True):
        """Corta a area transparente em volta e embute. Devolve a tag (ou None se vazia)."""
        a = rgba[..., 3] > 0
        if not a.any():
            return None
        ys, xs = np.nonzero(a.any(axis=1))[0], np.nonzero(a.any(axis=0))[0]
        y0, y1 = ys[0] // st.PX * st.PX, (ys[-1] // st.PX + 1) * st.PX
        x0, x1 = xs[0] // st.PX * st.PX, (xs[-1] // st.PX + 1) * st.PX
        mime, data = encode(np.ascontiguousarray(rgba[y0:y1, x0:x1]))
        self.bytes[ident] = len(data)
        tag = (f'<image id="{ident}" x="{x0 // st.SCALE}" y="{y0 // st.SCALE}" width="{(x1 - x0) // st.SCALE}" '
               f'height="{(y1 - y0) // st.SCALE}" href="data:{mime};base64,{base64.b64encode(data).decode()}"/>')
        if in_defs:
            self.defs.append(tag)
        return tag

    def windows(self, inner, intervals):
        """Mostra `inner` nos intervalos (s) do ciclo de 10 s, para sempre."""
        self.n += 1
        cls = f"k{self.n}"
        pts = {}
        for a, b in intervals:
            pts[round(a, 3)] = 1
            pts.setdefault(round(b, 3), 0)
        start = pts.get(0.0, 0)
        kf = [f'0%{{opacity:{start}}}']
        last = start
        for t in sorted(pts):
            if 0 < t < CYCLE:
                kf.append(f'{t / CYCLE * 100:.3f}%{{opacity:{pts[t]}}}')
                last = pts[t]
        kf.append(f'100%{{opacity:{0 if CYCLE in pts else last}}}')
        self.css.append(f'.{cls}{{animation:{cls} {CYCLE:g}s step-end infinite}}@keyframes {cls}{{{"".join(kf)}}}')
        self.body.append(f'<g class="h {cls}">{inner}</g>')


# ---------------------------------------------------------------- glitch
def clip_id(doc, r0, h, made=set()):
    key = f"c{r0}_{h}"
    if key not in made:
        made.add(key)
        doc.defs.append(f'<clipPath id="{key}"><rect x="0" y="{r0 * CELL}" width="{W}" height="{h * CELL}"/></clipPath>')
    return key


def glitch_frame(doc, src, bands, noise_rows):
    parts = [f'<g clip-path="url(#{clip_id(doc, r0, h)})"><use href="#{src}" x="{dx * CELL}"/></g>'
             for r0, h, dx in bands]
    parts += [f'<use href="#ruido" y="{r * CELL}"/>' for r in noise_rows]
    return ''.join(parts)


def noise_strip():
    rng = np.random.default_rng(3)
    g = rng.choice([st.IDX[n] for n in ['x', '0', '1', '#', '$', 'full', '>']], size=(2, bf.COLS))
    pal = np.array([(255, 255, 255), (255, 60, 150), (60, 255, 140), (120, 200, 255)])
    col = pal[rng.integers(0, len(pal), size=(2, bf.COLS))].astype(float)
    return st.render(g, col, rng.random((2, bf.COLS)) < 0.55)


# ---------------------------------------------------------------- glifos em vetor (trocas e brilho)
def glyph_paths(doc):
    for name in ['+', '1', 'x', '0', '$', '#', 'full', ':']:
        m = st._mask(name)[::st.SCALE, ::st.SCALE]
        d = []
        for y in range(CELL):
            x = 0
            while x < CELL:
                if m[y, x]:
                    x2 = x
                    while x2 < CELL and m[y, x2]:
                        x2 += 1
                    d.append(f"M{x} {y}h{x2 - x}v1h-{x2 - x}z")
                    x = x2
                else:
                    x += 1
        doc.defs.append(f'<path id="q{st.IDX[name]}" d="{"".join(d)}"/>')


def hexc(c):
    return '#%02x%02x%02x' % tuple(np.clip(c, 0, 255).astype(int))


def cell(r, c, gname, color):
    x, y = c * CELL, r * CELL
    return (f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" fill="#08090c"/>'
            f'<use href="#q{st.IDX[gname]}" x="{x}" y="{y}" fill="{color}"/>')


def bright_spot(frame, box):
    """Celula (linha, coluna) do pixel mais claro e sem cor dentro de box (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = box
    reg = frame[y0:y1, x0:x1].astype(int)
    mn = reg.min(axis=2)
    iy, ix = np.unravel_index(np.where(reg.max(axis=2) - mn < 40, mn, 0).argmax(), mn.shape)
    return int((iy + y0) / (bf.FH / bf.ROWS)), int((ix + x0) / (bf.FW / bf.COLS))


# ---------------------------------------------------------------- cenas em vai e volta
def pingpong(doc, prefix, states, t0, slot):
    """Base sempre por baixo; cada quadro k acende em t0+k*slot e apaga na volta, em
    t0+(2N-1-k)*slot. Como os quadros se empilham, apagar na ordem inversa e voltar no tempo."""
    n = len(states)
    cur_g, cur_c = states[0][0].copy(), states[0][1].copy()
    for k in range(1, n):
        g, col = states[k]
        changed = (g != cur_g) | (np.abs(col - cur_c).max(axis=2) > 30)
        if not changed.any():
            continue
        cur_g[changed], cur_c[changed] = g[changed], col[changed]
        tag = doc.image(f'{prefix}d{k}', st.render(g, col, changed), in_defs=False)
        if tag:
            doc.windows(tag, [(t0 + k * slot, t0 + (2 * n - 1 - k) * slot)])


def swaps(doc, picks, colors, t_from, t_to, rng, glyph_seq):
    """Grupos de celulas que trocam de caractere por um instante, espalhados em [t_from, t_to)."""
    groups = [picks[i::10] for i in range(10)]
    for gi, cells in enumerate(groups):
        if not len(cells):
            continue
        for rep in range(2):                                   # cada grupo troca duas vezes por cena
            p = t_from + ((gi * 0.43 + rep * 2.1 + rng.random() * 0.2) % (t_to - t_from - 0.4))
            for step, gname_of in enumerate(glyph_seq):
                parts = ''.join(cell(r, c, gname_of(rng), hexc(colors(r, c, step))) for r, c in cells)
                doc.windows(parts, [(p + step * 0.18, p + (step + 1) * 0.18)])


# ---------------------------------------------------------------- montagem
def main(video, out_path):
    frames, n = bf.read_frames(video, set(S1_FRAMES) | set(S2_FRAMES))
    assert n == bf.NFRAMES, n
    bf.clean_scene1(frames)
    # cena 2: a legenda e a mesma o tempo todo; apaga no primeiro quadro e copia o remendo
    base2 = frames[bf.CUT1]
    m2 = bf.subtitle_mask(base2, bf.SUB_BOTTOM)
    fixed = bf.inpaint_subtitle(base2, bf.SUB_BOTTOM)
    for i in S2_FRAMES:
        frames[i][m2] = fixed[m2]

    s1 = [st.literal(bf.to_cells(frames[i], bf.COLS, bf.ROWS)) for i in S1_FRAMES]
    s2 = [st.literal(bf.to_cells(frames[i], bf.COLS, bf.ROWS)) for i in S2_FRAMES]
    centers = palette([col[g >= 0] for g, col in s1 + s2])
    s1 = [(g, snap(col, centers)) for g, col in s1]
    s2 = [(g, snap(col, centers)) for g, col in s2]

    doc = Doc()
    glyph_paths(doc)
    doc.image('ruido', noise_strip())

    # cena 1 por baixo de tudo (e o que fica se a animacao nao rodar); cena 2 por cima na metade dela
    doc.image('s1', st.render(*s1[0]))
    doc.image('s2', st.render(*s2[0]))
    doc.body.append('<use href="#s1"/>')
    pingpong(doc, 's1', s1, 0.0, S1_SLOT)
    doc.windows('<use href="#s2"/>', [(HALF, CYCLE)])
    pingpong(doc, 's2', s2, HALF, S2_SLOT)

    rng = np.random.default_rng(11)
    # cena 1: alguns caracteres claros trocando, e o brilho de estrela da direita piscando
    g1, c1 = s1[0]
    tone1, _, _ = bf.features(bf.to_cells(frames[0], bf.COLS, bf.ROWS))
    cand = np.argwhere((g1 >= st.IDX['1']) & (g1 != st.IDX['full']) & (tone1 > 0.55))
    picks = cand[rng.choice(len(cand), min(30, len(cand)), replace=False)]
    swaps(doc, picks, lambda r, c, step: c1[r, c] * (1.25 if step == 0 else 1.0), 0.5, 4.7, rng,
          [lambda q: 'x', lambda q: str(q.choice(['1', '0', '$']))])
    sr, sc = bright_spot(frames[0], (700, 150, 900, 300))
    arms = ''.join(cell(sr + dr, sc + dc, '+', '#ffe8cc') for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)))
    doc.windows(cell(sr, sc, 'full', '#fffaf2') + arms,
                [(t, t + 0.3) for t in (0.9, 2.3, 3.7)])

    # cena 2: o brilho da juba (rosa) piscando em bloco claro e voltando em outro caractere
    g2, c2 = s2[0]
    raw2 = bf.to_cells(frames[bf.CUT1], bf.COLS, bf.ROWS)
    _, _, sat2 = bf.features(raw2)
    cand = np.argwhere((sat2 > 0.5) & (raw2[..., 0] > 150) & (raw2[..., 2] > raw2[..., 1]))
    picks = cand[rng.choice(len(cand), min(70, len(cand)), replace=False)]
    swaps(doc, picks, lambda r, c, step: np.array([255, 205, 232]) if step == 0 else c2[r, c] * 1.15,
          HALF + 0.4, CYCLE - 0.3, rng, [lambda q: 'full', lambda q: str(q.choice(['0', 'x', '$', '#']))])

    # glitch nos cortes; o quadro 0 fica limpo (e o que aparece onde a animacao nao roda)
    cuts = [
        (0.080, 0.10, 's2', [(6, 3, -7), (15, 5, 9), (27, 2, -4), (38, 4, 12), (47, 3, -6)], [21, 44]),
        (0.180, 0.10, 's1', [(10, 4, 5), (30, 3, -8), (41, 2, 4)], [33]),
        (0.280, 0.10, 's1', [(24, 2, -3), (44, 2, 2)], []),
        (HALF - 0.10, 0.10, 's1', [(8, 4, 10), (22, 3, -12), (35, 5, 6)], [30]),
        (HALF, 0.067, 's1', [(12, 6, -9), (30, 4, 14), (44, 3, -5)], [20, 40]),
        (HALF + 0.067, 0.10, 's2', [(18, 3, 6), (38, 2, -4)], []),
        (CYCLE - 0.10, 0.10, 's2', [(6, 3, -8), (20, 5, 11), (41, 3, -6)], [33]),
    ]
    for t0, dur, src, bands, noise in cuts:
        doc.windows(glitch_frame(doc, src, bands, noise), [(t0, t0 + dur)])

    css = ('.h{opacity:0}' + ''.join(doc.css) +
           '@media (prefers-reduced-motion:reduce){*{animation:none!important}}')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'role="img" aria-label="Mosaico de caracteres animado com cenas de Cyberpunk: Edgerunners 2">'
           f'<title>Mosaico animado (fan art de Cyberpunk: Edgerunners 2)</title>'
           f'<style>{css}</style><defs>{"".join(doc.defs)}</defs>'
           f'<rect width="{W}" height="{H}" fill="#08090c"/>{"".join(doc.body)}</svg>')
    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(svg)
    print(f"svg: {len(svg.encode()) / 1024:.0f} KB  (imagens {sum(doc.bytes.values()) / 1024:.0f} KB antes do base64)")
    print(f"cena 1: {len(S1_FRAMES)} quadros, {(2 * len(S1_FRAMES) - 1) * S1_SLOT:.2f} s;"
          f" cena 2: {len(S2_FRAMES)} quadros, {(2 * len(S2_FRAMES) - 1) * S2_SLOT:.2f} s; estrela em {sr},{sc}")


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
