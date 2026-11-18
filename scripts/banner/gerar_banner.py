"""Gera o banner do README: mosaico animado em SVG a partir do video.

O video (4,2 s) toca uma vez so: o rapaz no escuro, os raios de luz chegando e ele olhando para a luz.
Para no ultimo quadro e continua vivo: brilho correndo pelos raios, poeira cintilando na nevoa,
o olho verde brilhando, alguns caracteres trocando e um glitch rapido de vez em quando.
Onde a animacao nao roda (ou com movimento reduzido), aparece o ultimo quadro parado.
O video nao vai para o repositorio (e material do anime e pesa): passe o caminho dele.
Depois, scripts/readme/gerar_visual.py poe a moldura e grava tema/banner.svg.

uso: python scripts/banner/gerar_banner.py VIDEO.mp4 MOSAICO.svg
"""
import base64
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
import numpy as np
from PIL import Image

import ceu
import mosaico as st
import video as bf

CELL = st.CELL
W, H = bf.COLS * CELL, bf.ROWS * CELL                       # 800 x 448
FPS = 30
T_END = bf.NFRAMES / FPS                                    # 4,2 s: o video para aqui
HOLD = 8.0                                                  # ciclo dos detalhes depois que para
FLOW, FLOW_STEPS, FLOW_SPACE = 3.0, 18, 36                  # brilho nos raios: periodo, passos, distancia (celulas)


# ---------------------------------------------------------------- cores: paleta unica
def palette(colors, k=112):
    allc = np.concatenate([x.reshape(-1, 3) for x in colors]).astype(np.float32)
    rng = np.random.default_rng(0)
    allc = allc[rng.choice(len(allc), min(len(allc), 30000), replace=False)]
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

    def once(self, inner, t_on, t_off):
        """Mostra `inner` de t_on a t_off (s), uma vez so."""
        self.n += 1
        cls = f"k{self.n}"
        self.css.append(f'.{cls}{{animation:on {t_off - t_on:.3f}s step-end {t_on:.3f}s forwards}}')
        self.body.append(f'<g class="h {cls}">{inner}</g>')

    def loop(self, inner, intervals, period, delay=None):
        """Mostra `inner` nos intervalos (s, dentro do periodo), para sempre, a partir de `delay`."""
        delay = T_END if delay is None else delay
        self.n += 1
        cls = f"k{self.n}"
        pts = {}
        for a, b in intervals:
            a, b = a % period, a % period + (b - a)
            parts = [(a, b)] if b <= period else [(a, period), (0.0, b - period)]
            for x, y in parts:
                pts[round(x, 3)] = 1
                pts.setdefault(round(y, 3), 0)
        start = pts.get(0.0, 0)
        kf = [f'0%{{opacity:{start}}}']
        last = start
        for t in sorted(pts):
            if 0 < t < period:
                kf.append(f'{t / period * 100:.3f}%{{opacity:{pts[t]}}}')
                last = pts[t]
        kf.append(f'100%{{opacity:{start if round(period, 3) in pts else last}}}')
        self.css.append(f'.{cls}{{animation:{cls} {period:g}s step-end {delay:.3f}s infinite}}'
                        f'@keyframes {cls}{{{"".join(kf)}}}')
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


# ---------------------------------------------------------------- glifos em vetor (trocas e brilhos)
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


FUNDO_CELULAS = np.zeros((bf.ROWS, bf.COLS), bool)          # o ceu no quadro final (main preenche)
CEU_GLIFO = np.array([78, 118, 196.0])                      # caractere no ceu escuro: azul, nao o verde do video


def cell(r, c, gname, color):
    x, y = c * CELL, r * CELL
    bg = hexc(st.FUNDO) if FUNDO_CELULAS[r, c] else '#08090c'
    return (f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" fill="{bg}"/>'
            f'<use href="#q{st.IDX[gname]}" x="{x}" y="{y}" fill="{color}"/>')


# ---------------------------------------------------------------- o video, uma vez
def playback(doc, states):
    """Quadro 0 inteiro e, por cima, so as celulas que mudam em cada quadro (caractere, cor ou ceu);
    tudo some em T_END e fica a base (o estado final acumulado, igual ao ultimo quadro)."""
    doc.image('v0', st.render(states[0][0], states[0][1], fundo=states[0][2]))
    doc.once('<use href="#v0"/>', 0.0, T_END)
    cur_g, cur_c, cur_f = (x.copy() for x in states[0])
    for k in range(1, len(states)):
        g, col, f = states[k]
        changed = (g != cur_g) | (np.abs(col - cur_c).max(axis=2) > 30) | (f != cur_f)
        if not changed.any():
            continue
        cur_g[changed], cur_c[changed], cur_f[changed] = g[changed], col[changed], f[changed]
        tag = doc.image(f'v{k}', st.render(g, col, changed, fundo=f), in_defs=False)
        if tag:
            doc.once(tag, k / FPS, T_END)
    return cur_g, cur_c, cur_f


# ---------------------------------------------------------------- depois que para
def beam_direction(luma, beam):
    """Direcao dos raios (perpendicular ao gradiente dominante nas celulas de raio), apontando para a direita."""
    l = cv2.GaussianBlur(luma.astype(np.float32), (0, 0), 1.0)
    gy, gx = np.gradient(l)
    jxx, jyy, jxy = (gx * gx)[beam].sum(), (gy * gy)[beam].sum(), (gx * gy)[beam].sum()
    w, v = np.linalg.eigh(np.array([[jxx, jxy], [jxy, jyy]]))
    dx, dy = v[:, 0]                                        # menor autovalor: ao longo do raio
    return (dx, dy) if dx >= 0 else (-dx, -dy)


def ray_flow(doc, g, col, raw):
    """Pulsos de luz correndo pelos raios, para o lado de fora da luz (para a direita e para baixo).
    Quando o pulso passa, o miolo fica branco e o raio engrossa; atras dele fica um rastro mais fraco."""
    _, luma, _ = bf.features(raw)
    light, core, ridge = st.light_masks(raw)
    rf = st.ray_over_face(raw)                              # o raio por cima do rosto: o pulso passa, sem engrossar
    swell = (cv2.dilate(core.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0) & (luma > 0.3) & ~rf
    beam = swell | (light & (ridge > 0.02)) | rf
    dx, dy = beam_direction(luma, core | (light & (ridge > 0.02)))
    rr, cc = np.mgrid[0:bf.ROWS, 0:bf.COLS]
    p = cc * dx + rr * dy                                   # posicao ao longo do raio
    n_lab, lab = cv2.connectedComponents(beam.astype(np.uint8), connectivity=8)
    off = st.hash01(lab, 0, 7) * FLOW_SPACE                 # cada raio com sua fase
    phase = np.floor(((p - off) % FLOW_SPACE) / FLOW_SPACE * FLOW_STEPS).astype(int)
    step = FLOW / FLOW_STEPS
    denser = np.arange(len(st.NAMES))                       # glifo um degrau mais cheio
    for a, b in zip(st.RAMP, st.RAMP[1:]):
        denser[st.IDX[a]] = st.IDX[b]
    ones = np.ones_like(col)
    gl = np.where(g >= 0, g, st.IDX['+'])
    peak_g = np.where(swell, st.IDX['full'], denser[gl])
    peak_c = np.where(core[..., None], np.array([255, 253, 240.0]) * ones,
                      np.where(swell[..., None], np.array([255, 236, 175.0]) * ones, np.array([255, 242, 200.0]) * ones))
    tail_g = np.where(core, st.IDX['full'], gl)
    tail_c = np.where(core[..., None], np.array([255, 247, 215.0]) * ones, np.minimum(col * 1.3 + 25, 255))
    for k in range(FLOW_STEPS):
        grp = beam & (phase == k)
        tag = doc.image(f'fp{k}', st.render(tail_g, tail_c, grp, fundo=FUNDO_CELULAS), in_defs=False)
        if tag:
            doc.loop(tag, [((k + 3) * step, (k + 6) * step)], FLOW)
        tag = doc.image(f'fq{k}', st.render(peak_g, peak_c, grp, fundo=FUNDO_CELULAS), in_defs=False)
        if tag:
            doc.loop(tag, [(k * step, (k + 3) * step)], FLOW)
    print(f"raios: direcao ({dx:.2f}, {dy:.2f}), {int(beam.sum())} celulas em {n_lab - 1} raios")


def dust(doc, g, raw, rng):
    """Poeira cintilando na nevoa (claro e quente, fora do miolo dos raios)."""
    light, core, ridge = st.light_masks(raw)
    cand = np.argwhere(light & ~core & (ridge < 0.03))
    picks = cand[rng.choice(len(cand), min(48, len(cand)), replace=False)]
    for gi in range(16):
        cells = picks[gi::16]
        for rep in range(2):
            t = (gi * 0.5 + rep * 4.1 + rng.random() * 0.3) % (HOLD - 0.5)
            doc.loop(''.join(cell(r, c, 'full', '#fff8e6') for r, c in cells), [(t, t + 0.12)], HOLD)
            doc.loop(''.join(cell(r, c, '+', '#ffe6a8') for r, c in cells), [(t + 0.12, t + 0.36)], HOLD)


def swaps(doc, g, col, raw, rng):
    """Alguns caracteres do rosto e da roupa trocando por um instante."""
    light, _, _ = st.light_masks(raw)
    cand = np.argwhere(~light & (g >= st.IDX['1']) & (g <= st.IDX['#']))
    picks = cand[rng.choice(len(cand), min(30, len(cand)), replace=False)]
    for gi in range(10):
        cells = picks[gi::10]
        for rep in range(2):
            t = (gi * 0.71 + rep * 3.7 + rng.random() * 0.2) % (HOLD - 0.6)
            doc.loop(''.join(cell(r, c, 'x', hexc(col[r, c] * 1.25)) for r, c in cells), [(t, t + 0.18)], HOLD)
            doc.loop(''.join(cell(r, c, str(rng.choice(['1', '0', '$'])), hexc(col[r, c])) for r, c in cells),
                     [(t + 0.18, t + 0.36)], HOLD)


# ---------------------------------------------------------------- montagem
def main(video, out_path):
    frames, n = bf.read_frames(video, set(range(bf.NFRAMES)))
    assert n == bf.NFRAMES, n
    bf.clean_subtitles(frames)
    raws = [bf.to_cells(frames[i]) for i in range(n)]
    skies = ceu.sky_masks([frames[i] for i in range(n)])
    states = []
    for i, c in enumerate(raws):
        g, col = st.luz(c, frames[i], skies[i])
        light, _, _ = st.light_masks(c)
        dark_sky = skies[i] & ~light & ~st.ray_over_face(c) & (g >= 0)
        _, luma, _ = bf.features(c)
        k = np.clip(0.45 + luma * 2.5, 0.45, 1.0)[..., None]
        col = np.where(dark_sky[..., None], CEU_GLIFO * k, col)
        states.append((g, col, skies[i]))
    centers = palette([col[g >= 0] for g, col, _ in states])

    states = [(g, snap(col, centers), f) for g, col, f in states]

    doc = Doc()
    glyph_paths(doc)
    doc.image('ruido', noise_strip())

    g_end, c_end, f_end = playback(doc, states)
    FUNDO_CELULAS[:] = f_end
    doc.image('fim', st.render(g_end, c_end, fundo=FUNDO_CELULAS))
    doc.body.insert(0, '<use href="#fim"/>')                # por baixo de tudo: e o que fica

    # entrada: glitch que estabiliza (o primeiro lampejo e do quadro final)
    for t0, dur, src, bands, noise in [
        (0.080, 0.10, 'fim', [(6, 3, -7), (15, 5, 9), (27, 2, -4), (38, 4, 12), (47, 3, -6)], [21, 44]),
        (0.180, 0.10, 'v0', [(10, 4, 5), (30, 3, -8), (41, 2, 4)], [33]),
        (0.280, 0.10, 'v0', [(24, 2, -3), (44, 2, 2)], []),
    ]:
        doc.once(glitch_frame(doc, src, bands, noise), t0, t0 + dur)

    # depois que para
    rng = np.random.default_rng(11)
    raw = raws[-1]
    ray_flow(doc, g_end, c_end, raw)
    dust(doc, g_end, raw, rng)
    swaps(doc, g_end, c_end, raw, rng)
    eye = st.is_eye(raw)
    if eye.any():
        er, ec = np.unravel_index(np.where(eye, raw[..., 1] - raw[..., 0], -1).argmax(), eye.shape)
        arms = ''.join(cell(er + a, ec + b, '+', '#c8ffd8') for a, b in ((-1, 0), (1, 0), (0, -1), (0, 1)))
        doc.loop(cell(er, ec, 'full', '#eafff0') + arms, [(t, t + 0.3) for t in (1.1, 5.3)], HOLD)
    for t0, dur, bands, noise in [
        (6.40, 0.10, [(8, 4, 10), (22, 3, -12), (35, 5, 6)], [30]),
        (6.50, 0.067, [(12, 6, -9), (30, 4, 14), (44, 3, -5)], [20, 40]),
    ]:
        doc.loop(glitch_frame(doc, 'fim', bands, noise), [(t0, t0 + dur)], HOLD)

    css = ('.h{opacity:0}@keyframes on{0%{opacity:1}100%{opacity:0}}' + ''.join(doc.css) +
           '@media (prefers-reduced-motion:reduce){*{animation:none!important}}')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'role="img" aria-label="Mosaico de caracteres animado com uma cena de Cyberpunk: Edgerunners 2">'
           f'<title>Mosaico animado (fan art de Cyberpunk: Edgerunners 2)</title>'
           f'<style>{css}</style><defs>{"".join(doc.defs)}</defs>'
           f'<rect width="{W}" height="{H}" fill="#08090c"/>{"".join(doc.body)}</svg>')
    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(svg)
    play = sum(v for k, v in doc.bytes.items() if k.startswith('v'))
    print(f"ceu: {int(skies[0].sum())} celulas no quadro 0, {int(FUNDO_CELULAS.sum())} no final")
    print(f"svg: {len(svg.encode()) / 1024:.0f} KB  (imagens {sum(doc.bytes.values()) / 1024:.0f} KB antes do base64;"
          f" video {play / 1024:.0f} KB)  camadas: {doc.n}")


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
