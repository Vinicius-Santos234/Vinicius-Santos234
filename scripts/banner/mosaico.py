"""Glifos, mapeamento de tom para glifo e desenho das celulas em imagem (2x)."""
import numpy as np
from PIL import Image

CELL, SCALE = 8, 2
PX = CELL * SCALE                      # 16 px por celula na imagem
BG = (8, 9, 12)
DOT = (30, 32, 40)

G = {
    'dot':  ["00000", "00000", "00100", "00000", "00000"],
    '.':    ["00000", "00000", "00000", "00110", "00110"],
    ':':    ["00000", "00100", "00000", "00100", "00000"],
    '+':    ["00000", "00100", "01110", "00100", "00000"],
    '>':    ["01000", "00100", "00010", "00100", "01000"],
    '1':    ["00100", "01100", "00100", "00100", "01110"],
    'x':    ["10001", "01010", "00100", "01010", "10001"],
    '0':    ["01110", "10011", "10101", "11001", "01110"],
    '$':    ["01111", "10100", "01110", "00101", "11110"],
    '#':    ["01010", "11111", "01010", "11111", "01010"],
    'full': None,
}
RAMP = ['.', ':', '+', '>', '1', 'x', '0', '$', '#']
NAMES = list(G)
IDX = {n: i for i, n in enumerate(NAMES)}


def _mask(name):
    m = np.zeros((CELL, CELL), bool)
    if name == 'full':
        m[1:7, 1:7] = True
    else:
        m[1:6, 1:6] = np.array([[ch == '1' for ch in row] for row in G[name]])
    return np.kron(m, np.ones((SCALE, SCALE), bool))


MASKS = [_mask(n) for n in NAMES]


def hash01(r, c, salt=0):
    """Ruido deterministico por celula, 0..1."""
    v = (np.asarray(r) * 73856093) ^ (np.asarray(c) * 19349663) ^ (salt * 83492791)
    return ((v % 1000003) / 1000003.0)


def boost(col, lo=0.35, gain=1.12):
    """Clareia a cor do glifo: o glifo acende so parte da celula, entao a cor precisa ser forte."""
    mx = col.max(axis=-1, keepdims=True)
    k = gain * 255 / np.maximum(mx, lo * 255)
    return np.clip(col * np.minimum(k, 2.2), 0, 255)


def tone_glyphs(tone, sat, block_tone=0.93, block_sat=0.5, light_cap=None, luma=None):
    """Tom 0..1 -> indice de glifo (-1 = vazio, so o ponto da grade)."""
    t = np.clip(tone, 0, 1)
    k = np.clip(((t - 0.08) / 0.84 * len(RAMP)).astype(int), 0, len(RAMP) - 1)
    out = np.array([IDX[RAMP[i]] for i in k.ravel()]).reshape(t.shape)
    if light_cap is not None:                       # claro e sem cor: nao passa do glifo dado
        capped = (luma > 0.62) & (sat < 0.42)
        out = np.where(capped & (out > IDX[light_cap]), IDX[light_cap], out)
    blocks = ((t >= block_tone) & (sat >= block_sat)) | (t >= 0.985)
    out = np.where(blocks, IDX['full'], out)
    out = np.where(t < 0.08, -1, out)
    return out


MASK_ARR = np.stack(MASKS)


def literal(c):
    """Densidade pelo tom, claro e sem cor para no '0', bloco so no brilho saturado (o glitter da juba)."""
    from video import features
    tone, luma, sat = features(c)
    rr, cc = np.mgrid[0:c.shape[0], 0:c.shape[1]]
    g = tone_glyphs(tone, sat, block_tone=2, block_sat=2, light_cap='0', luma=luma)
    v = c.max(axis=2) / 255
    g = np.where((v > 0.80) & (sat > 0.5) & (hash01(rr, cc, 5) < 0.45), IDX['full'], g)
    return g, boost(c, lo=0.12, gain=1.1)


def render(glyph, color, present=None, dots=True):
    """glyph (R,C) int, color (R,C,3). present=False deixa a celula transparente.
    Celula presente = quadrado de fundo opaco + glifo; devolve RGBA."""
    R, C = glyph.shape
    if present is None:
        present = np.ones((R, C), bool)
    empty = glyph < 0
    m = MASK_ARR[np.where(empty, IDX['dot'], glyph)].copy()           # (R, C, PX, PX)
    if not dots:
        m[empty] = False
    col = np.where(empty[..., None], np.array(DOT, float), np.clip(color, 0, 255)).astype(np.uint8)
    rgb = np.where(m[..., None], col[:, :, None, None, :], np.array(BG, np.uint8))
    a = np.broadcast_to((present * 255).astype(np.uint8)[:, :, None, None, None], (R, C, PX, PX, 1))
    img = np.concatenate([rgb, a], axis=-1)
    img[~present] = 0
    return np.ascontiguousarray(img.transpose(0, 2, 1, 3, 4).reshape(R * PX, C * PX, 4))
