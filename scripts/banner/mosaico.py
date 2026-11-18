"""Glifos, mapeamento de tom para glifo e desenho das celulas em imagem (2x)."""
import numpy as np
from PIL import Image

CELL, SCALE = 8, 2
PX = CELL * SCALE                      # 16 px por celula na imagem
BG = (8, 9, 12)                        # fundo da celula com caractere (o personagem)
DOT = (30, 32, 40)
FUNDO = (17, 28, 52)                   # o fundo da cena (atras dele), azul-escuro
FUNDO_DOT = (46, 68, 110)

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
    '-':    ["00000", "00000", "11111", "00000", "00000"],
    '|':    ["00100", "00100", "00100", "00100", "00100"],
    '/':    ["00001", "00010", "00100", "01000", "10000"],
    '\\':   ["10000", "01000", "00100", "00010", "00001"],
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


def render(glyph, color, present=None, dots=True, fundo=None):
    """glyph (R,C) int, color (R,C,3). present=False deixa a celula transparente.
    fundo (R,C) bool: celulas do fundo da cena, com o quadrado azul-escuro em vez do quase-preto.
    Celula presente = quadrado de fundo opaco + glifo; devolve RGBA."""
    R, C = glyph.shape
    if present is None:
        present = np.ones((R, C), bool)
    empty = glyph < 0
    m = MASK_ARR[np.where(empty, IDX['dot'], glyph)].copy()           # (R, C, PX, PX)
    if not dots:
        m[empty] = False
    if fundo is None:
        fundo = np.zeros((R, C), bool)
    dot = np.where(fundo[..., None], np.array(FUNDO_DOT, float), np.array(DOT, float))
    col = np.where(empty[..., None], dot, np.clip(color, 0, 255)).astype(np.uint8)
    bg = np.where(fundo[..., None], np.array(FUNDO, np.uint8), np.array(BG, np.uint8))
    rgb = np.where(m[..., None], col[:, :, None, None, :], bg[:, :, None, None, :])
    a = np.broadcast_to((present * 255).astype(np.uint8)[:, :, None, None, None], (R, C, PX, PX, 1))
    img = np.concatenate([rgb, a], axis=-1)
    img[~present] = 0
    return np.ascontiguousarray(img.transpose(0, 2, 1, 3, 4).reshape(R * PX, C * PX, 4))


GOLD = np.array([255, 222, 150], float)


def _satboost(c, k):
    l = c.mean(axis=-1, keepdims=True)
    return np.clip(l + (c - l) * k, 0, 255)


def is_eye(c):
    """Iris verde (nao o ciano do visor de cristal): G bem acima de R e de B."""
    from video import features
    _, luma, _ = features(c)
    return ((c[..., 1] - c[..., 0]) > 17) & ((c[..., 1] - c[..., 2]) > 10) & (luma > 0.35)


def light_masks(c):
    """Luz (raios e nevoa: claro e quente) e o miolo dos raios (mais claro que a vizinhanca)."""
    import cv2
    from video import features
    _, luma, _ = features(c)
    warm = (c[..., 0] + c[..., 1]) / 2 - c[..., 2]
    green = c[..., 1] - c[..., 0]                   # o olho verde nao e luz
    ridge = luma - cv2.GaussianBlur(luma.astype(np.float32), (0, 0), 2.5)
    light = (luma > 0.42) & (warm > 7) & (green < 12)
    core = light & (ridge > 0.07) & (luma > 0.55)
    return light, core, ridge


def tracos(rgb, c, forte=0.14, minimo=4):
    """Traco escuro do desenho (olho, nariz, boca, mechas) sobre pele clara: celula e direcao do traco.
    O traco tem 1 a 2 px, entao a media da celula o dilui: conta os pixels de traco forte (black-hat,
    fechamento - original) numa grade de 10x10 px por celula. O tensor de estrutura da a direcao."""
    import cv2
    R, C = c.shape[:2]
    P = 10
    big = cv2.resize(rgb, (C * P, R * P), interpolation=cv2.INTER_LINEAR)
    L = big.astype(np.float32).mean(axis=2) / 255
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    closed = cv2.morphologyEx(L, cv2.MORPH_CLOSE, k)
    bh = closed - L
    strong = (bh > forte) & (closed > 0.45)
    gx = cv2.Sobel(bh, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(bh, cv2.CV_32F, 0, 1, ksize=3)

    def per_cell(img, how=np.sum):
        return how(img.reshape(R, P, C, P), axis=(1, 3))
    count = per_cell(strong.astype(np.int32))
    jxx, jyy, jxy = per_cell(gx * gx), per_cell(gy * gy), per_cell(gx * gy)
    phi = 0.5 * np.degrees(np.arctan2(2 * jxy, jxx - jyy))            # direcao do gradiente
    ang = (phi + 90) % 180                                             # direcao do traco (y para baixo)
    gl = np.full((R, C), IDX['-'])
    gl = np.where((ang >= 22.5) & (ang < 67.5), IDX['\\'], gl)
    gl = np.where((ang >= 67.5) & (ang < 112.5), IDX['|'], gl)
    gl = np.where((ang >= 112.5) & (ang < 157.5), IDX['/'], gl)
    light, _, _ = light_masks(c)
    line = (count >= minimo) & (per_cell(closed, np.mean) > 0.45) & ~light
    return line, gl, count


def ray_over_face(c):
    """Raio passando por cima do rosto: a pele e clara e fria (brilho ~0,62, quente ~ -2); com o raio por
    cima fica bem mais clara e levemente quente (~0,85, +2 a +6), sem chegar no quente da nevoa."""
    from video import features
    _, luma, _ = features(c)
    warm = (c[..., 0] + c[..., 1]) / 2 - c[..., 2]
    light, _, _ = light_masks(c)
    return (luma > 0.74) & (warm >= 1) & ((c[..., 1] - c[..., 0]) < 12) & ~light & ~is_eye(c)


def shadow_skin(c, light):
    """O lado do rosto na sombra (o da orelha): cinza medio e uniforme (~0,23) encostado na pele iluminada."""
    import cv2
    from video import features
    tone, luma, sat = features(c)
    warm = (c[..., 0] + c[..., 1]) / 2 - c[..., 2]
    red = (c[..., 0] > c[..., 1] * 1.3) & (c[..., 0] > 90)
    lit = (luma > 0.5) & (warm < 7) & (sat < 0.3) & ~red
    neutral = (c[..., 1] - c[..., 2]) < 6                 # a pele na sombra e cinza neutro; o cabelo puxa pro verde
    mid = (luma >= 0.17) & (luma <= 0.36) & (sat < 0.3) & (np.abs(warm) < 8) & neutral & ~light & ~red
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mid.astype(np.uint8), connectivity=4)
    near = cv2.dilate(lit.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    keep = [k for k in range(1, n) if stats[k, cv2.CC_STAT_AREA] >= 6 and near[lab == k].any()]
    return np.isin(lab, keep)


def face_zone(c, light, sh, rf, eye):
    """A regiao do rosto: pele iluminada, pele na sombra, raio por cima do rosto, tinta e olho, com as mechas
    que cruzam a testa preenchidas (fechamento + buracos) e uma celula de folga na borda. Ali a armadura nao entra."""
    import cv2
    from video import features
    tone, luma, sat = features(c)
    warm = (c[..., 0] + c[..., 1]) / 2 - c[..., 2]
    redish = (c[..., 0] > c[..., 1] * 1.25) & (c[..., 0] > 45)
    lit = (luma > 0.5) & (warm < 7) & (sat < 0.3) & ~redish
    core = (lit | sh | rf | redish | eye).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(core, connectivity=8)
    big = np.isin(lab, [k for k in range(1, n) if stats[k, cv2.CC_STAT_AREA] >= 15])
    z = cv2.morphologyEx(big.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    # preenche buracos (o que nao encosta na borda do quadro por fora)
    inv = (1 - z).astype(np.uint8)
    nn, lab2 = cv2.connectedComponents(inv, connectivity=4)
    border = set(np.unique(np.concatenate([lab2[0], lab2[-1], lab2[:, 0], lab2[:, -1]])))
    holes = ~np.isin(lab2, list(border)) & (inv > 0)
    z = (z > 0) | holes
    return cv2.dilate(z.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0


def armor_edges(rgb, c, forte=0.05, minimo=4):
    """Contorno claro e fino sobre o escuro (as bordas das placas da armadura, das mechas e da orelha):
    top-hat (original - abertura) contado numa grade de 10x10 px por celula; direcao pelo tensor de estrutura."""
    import cv2
    R, C = c.shape[:2]
    P = 10
    big = cv2.resize(rgb, (C * P, R * P), interpolation=cv2.INTER_LINEAR)
    L = big.astype(np.float32).mean(axis=2) / 255
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    opened = cv2.morphologyEx(L, cv2.MORPH_OPEN, k)
    th = L - opened
    strong = (th > forte) & (opened < 0.3)
    gx = cv2.Sobel(th, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(th, cv2.CV_32F, 0, 1, ksize=3)

    def per_cell(img, how=np.sum):
        return how(img.reshape(R, P, C, P), axis=(1, 3))
    count = per_cell(strong.astype(np.int32))
    jxx, jyy, jxy = per_cell(gx * gx), per_cell(gy * gy), per_cell(gx * gy)
    ang = (0.5 * np.degrees(np.arctan2(2 * jxy, jxx - jyy)) + 90) % 180
    gl = np.full((R, C), IDX['-'])
    gl = np.where((ang >= 22.5) & (ang < 67.5), IDX['\\'], gl)
    gl = np.where((ang >= 67.5) & (ang < 112.5), IDX['|'], gl)
    gl = np.where((ang >= 112.5) & (ang < 157.5), IDX['/'], gl)
    peak = per_cell(np.where(strong, L, 0), np.max)
    return (count >= minimo) & (per_cell(opened, np.mean) < 0.3), gl, peak


ARMADURA = np.array([150, 172, 188.0])                  # cinza-azulado das placas e dos contornos


def luz(c, rgb=None, sky=None):
    """O literal() das cenas antigas, mais a luz: raios e nevoa puxados para o dourado, bloco so no
    miolo dos raios, tinta vermelha e olho verde com mais cor. No escuro (sem luz quente) fica igual."""
    from video import features
    g, _ = literal(c)
    tone, luma, sat = features(c)
    light, core, ridge = light_masks(c)
    cs = _satboost(c, 1.5)
    w = np.clip((luma - 0.42) / 0.3, 0, 1)[..., None] * light[..., None]
    gold = GOLD * np.clip(luma[..., None] * 1.15, 0, 1)
    cs = cs * (1 - 0.7 * w) + gold * (0.7 * w)
    rf = ray_over_face(c)                               # raio sobre o rosto: dourado, com o rosto por baixo
    cs = np.where(rf[..., None], cs * 0.2 + gold * 0.8, cs)
    red = (c[..., 0] > c[..., 1] * 1.3) & (c[..., 0] > 90)
    g = np.where(red & (g >= 0) & (g < IDX['x']), IDX['x'], g)
    eye = is_eye(c)                                     # olho verde: acento
    cs = np.where(eye[..., None], np.array([150, 255, 180], float), cs)
    g = np.where(eye & (g < IDX['0']), IDX['0'], g)
    if eye.any():
        gg = np.where(eye, c[..., 1] - c[..., 0], -1)
        g[np.unravel_index(gg.argmax(), gg.shape)] = IDX['full']
    haze = light & ~core & (ridge < 0.03)           # nevoa recua (ralo), para o raio e o rosto aparecerem
    g = np.where(haze & (g > IDX['1']), IDX['1'], g)
    g = np.where(core, IDX['full'], g)
    col = boost(cs, lo=0.12, gain=1.1)
    if sky is None:
        sky = np.zeros(g.shape, bool)
    # o lado do rosto na sombra: mais claro, para nao sumir no escuro
    sh = shadow_skin(c, light) & ~sky & ~eye
    t_sh = np.clip(tone + 0.22, 0, 1)
    g_sh = tone_glyphs(t_sh, sat, block_tone=2, block_sat=2, light_cap='0', luma=np.maximum(luma, 0.63))
    g = np.where(sh, g_sh, g)
    col = np.where(sh[..., None], np.clip(col * 1.45 + 18, 0, 255), col)
    # as placas da armadura (o escuro do personagem): tom levantado e cinza-azulado, cada placa com o seu
    redish = (c[..., 0] > c[..., 1] * 1.25) & (c[..., 0] > 45)       # a tinta vermelha no escuro fica vermelha
    face = face_zone(c, light, sh, rf, eye)                         # o rosto fica como era
    dark = (tone < 0.35) & ~light & ~sky & ~sh & ~eye & ~rf & ~redish & ~face
    # e a tinta no escuro ganha um pouco de forca, para nao se perder no meio das placas
    paint = redish & ~light & (tone < 0.45)
    g = np.where(paint & (g < IDX['+']), IDX['+'], g)
    col = np.where(paint[..., None], np.clip(col * 1.3, 0, 255), col)
    t_up = np.clip(tone, 0, 1) ** 0.55
    g_up = tone_glyphs(t_up, sat, block_tone=2, block_sat=2, light_cap='0', luma=luma)
    g = np.where(dark, g_up, g)
    target = np.clip(luma * 255 * 3.0 + 22, 0, 215)[..., None]     # brilho que a placa ganha
    own = col / np.maximum(col.max(axis=-1, keepdims=True), 1) * target   # a propria cor, so mais clara
    tint = ARMADURA / ARMADURA.max() * target
    col = np.where(dark[..., None], np.clip(own * 0.65 + tint * 0.35, 0, 255), col)
    if rgb is not None:                                 # contornos claros da armadura por cima
        edge, eg, peak = armor_edges(rgb, c)
        edge &= ~light & ~sky & ~eye & ~redish & ~sh & ~face   # a tinta tem riscos claros: nao e armadura
        g = np.where(edge, eg, g)
        col = np.where(edge[..., None], ARMADURA * np.clip(0.55 + peak[..., None] * 1.2, 0.55, 1.0), col)
    if rgb is not None:                                 # tracos do rosto por cima (mais escuros)
        line, gl, _ = tracos(rgb, c)
        line &= ~eye
        g = np.where(line, gl, g)
        col = np.where(line[..., None], col * 0.38, col)
    return g, col
