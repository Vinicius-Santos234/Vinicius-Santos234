"""Tema do README (inspirado no visual dos menus de Cyberpunk 2077): cores, fonte embutida,
formas com canto cortado e medida de texto para quebrar linha."""
import base64
import io
import os
import re
from functools import lru_cache

from fontTools import subset
from fontTools.ttLib import TTFont

_AQUI = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.environ.get('TEMA_FONTES') or os.path.join(_AQUI, 'fontes')
ICON_DIR = os.environ.get('TEMA_ICONES') or os.path.join(_AQUI, 'icones')

# cores tiradas do print do jogo
FUNDO = '#07080c'
PAINEL = '#0b0a0e'
SELECIONADO = '#3e2a2e'
VERMELHO = '#d33833'
VERMELHO_APAGADO = '#5a1d1d'
CIANO = '#4fd2da'
CIANO_CLARO = '#7ff4f8'
CIANO_APAGADO = '#2f8f96'
TEXTO = '#a9dfe2'
AMARELO = '#eaae27'

PESOS = {500: 'Rajdhani-Medium.ttf', 600: 'Rajdhani-SemiBold.ttf', 700: 'Rajdhani-Bold.ttf'}


@lru_cache(None)
def _font(weight):
    return TTFont(os.path.join(FONT_DIR, PESOS[weight]))


def largura(texto, tamanho, peso=500, espaco=0.0):
    f = _font(peso)
    cmap, hmtx, upm = f.getBestCmap(), f['hmtx'], f['head'].unitsPerEm
    adv = 0
    for ch in texto:
        g = cmap.get(ord(ch)) or cmap.get(ord('?'))
        adv += hmtx[g][0]
    return adv * tamanho / upm + espaco * max(len(texto) - 1, 0)


def quebrar(texto, tamanho, maximo, peso=500):
    linhas, atual = [], ''
    for palavra in texto.split():
        tentativa = (atual + ' ' + palavra).strip()
        if atual and largura(tentativa, tamanho, peso) > maximo:
            linhas.append(atual)
            atual = palavra
        else:
            atual = tentativa
    if atual:
        linhas.append(atual)
    return linhas


class Fontes:
    """Junta o texto usado por peso e embute so essas letras (WOFF em base64)."""

    def __init__(self):
        self.usado = {}

    def usar(self, texto, peso):
        self.usado.setdefault(peso, set()).update(texto)
        return texto

    def css(self):
        regras = []
        for peso, chars in sorted(self.usado.items()):
            fonte = TTFont(os.path.join(FONT_DIR, PESOS[peso]), recalcTimestamp=False)
            opts = subset.Options()
            opts.flavor = 'woff'
            opts.layout_features = ['kern', 'liga']
            s = subset.Subsetter(opts)
            s.populate(text=''.join(sorted(chars)) + ' ')
            s.subset(fonte)
            fonte.flavor = 'woff'
            buf = io.BytesIO()
            fonte.save(buf)
            b64 = base64.b64encode(buf.getvalue()).decode()
            regras.append(f"@font-face{{font-family:'R';font-weight:{peso};"
                          f"src:url(data:font/woff;base64,{b64}) format('woff')}}")
        return ''.join(regras)


def esc(t):
    return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def chanfro(x, y, w, h, c=10, cantos='tl br'):
    """Retangulo com cantos cortados em diagonal (os do jogo cortam em cima a esquerda e embaixo a direita)."""
    tl = c if 'tl' in cantos else 0
    tr = c if 'tr' in cantos else 0
    br = c if 'br' in cantos else 0
    bl = c if 'bl' in cantos else 0
    pts = [(x + tl, y), (x + w - tr, y), (x + w, y + tr), (x + w, y + h - br), (x + w - br, y + h),
           (x + bl, y + h), (x, y + h - bl), (x, y + tl)]
    return 'M' + ' L'.join(f'{px:g} {py:g}' for px, py in pts) + ' Z'


def texto(x, y, conteudo, tamanho, peso, cor, fontes, espaco=0, ancora='start', extra=''):
    fontes.usar(conteudo, peso)
    ls = f' letter-spacing="{espaco:g}"' if espaco else ''
    return (f'<text x="{x:g}" y="{y:g}" font-family="R,\'Rajdhani\',\'Arial Narrow\',sans-serif" font-size="{tamanho:g}" '
            f'font-weight="{peso}" fill="{cor}" text-anchor="{ancora}"{ls}{extra}>{esc(conteudo)}</text>')


def svg(w, h, corpo, fontes, titulo, extra_css=''):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{esc(titulo)}"><title>{esc(titulo)}</title>'
            f'<style>{fontes.css()}{extra_css}</style>'
            f'<rect width="{w}" height="{h}" fill="{FUNDO}"/>{corpo}</svg>')


# ------------------------------------------------------------------ icones
def simple_icon(slug):
    with open(os.path.join(ICON_DIR, f'{slug}.svg'), encoding='utf-8') as fh:
        return re.search(r'<path d="([^"]+)"', fh.read()).group(1)


# icones desenhados aqui, numa grade de 24 (traco)
ICONES = {
    'sobre': '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7"/>',
    'tecnologias': '<path d="M12 3 21 8 12 13 3 8Z"/><path d="M3 12.5 12 17.5 21 12.5"/><path d="M3 16.5 12 21.5 21 16.5"/>',
    'ia': '<rect x="6" y="6" width="12" height="12" rx="1"/><rect x="9.5" y="9.5" width="5" height="5"/>'
          '<path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
    'projetos': '<path d="M3 6h7l2 2h9v12H3Z"/><path d="M3 11h18"/>',
    'contato': '<rect x="3" y="5" width="18" height="14" rx="1"/><path d="m3 7 9 6 9-6"/>',
    'voz': '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3M8 21h8"/>',
    'visao': '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
    'agente': '<rect x="5" y="8" width="14" height="11" rx="2"/><path d="M12 8V4M9 13h.01M15 13h.01M9 16.5h6"/>'
              '<circle cx="12" cy="3.5" r="1"/>',
    'email': '<rect x="3" y="5" width="18" height="14" rx="1"/><path d="m3 7 9 6 9-6"/>',
    'linkedin': '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M8 10v7M8 7v.01M12 17v-7M12 13a3 3 0 0 1 6 0v4"/>',
    'atividade': '<path d="M3 12h4l2-6 4 12 2-6h6"/>',
}


def icone(nome, x, y, tam, cor, traco=1.6):
    s = tam / 24
    return (f'<g transform="translate({x:g} {y:g}) scale({s:g})" fill="none" stroke="{cor}" '
            f'stroke-width="{traco / s:g}" stroke-linecap="round" stroke-linejoin="round">{ICONES[nome]}</g>')


def icone_marca(slug, x, y, tam, cor):
    s = tam / 24
    return f'<path transform="translate({x:g} {y:g}) scale({s:g})" fill="{cor}" d="{simple_icon(slug)}"/>'


# os mesmos caracteres 5x5 do banner, para o mapa de atividade conversar com ele
GLIFOS = {
    'ponto': ["00000", "00000", "00100", "00000", "00000"],
    ':':     ["00000", "00100", "00000", "00100", "00000"],
    '+':     ["00000", "00100", "01110", "00100", "00000"],
    'x':     ["10001", "01010", "00100", "01010", "10001"],
    '#':     ["01010", "11111", "01010", "11111", "01010"],
    'bloco': ["11111", "11111", "11111", "11111", "11111"],
}


def glifo_defs(celula):
    """<path id="gX"> de cada glifo numa celula de lado `celula` (o glifo ocupa 5/8 dela)."""
    px = celula / 8
    out = []
    for nome, linhas in GLIFOS.items():
        d = []
        for y, linha in enumerate(linhas):
            x = 0
            while x < 5:
                if linha[x] == '1':
                    x2 = x
                    while x2 < 5 and linha[x2] == '1':
                        x2 += 1
                    d.append(f'M{(1.5 + x) * px:.2f} {(1.5 + y) * px:.2f}h{(x2 - x) * px:.2f}v{px:.2f}h-{(x2 - x) * px:.2f}z')
                    x = x2
                else:
                    x += 1
        ident = {'ponto': 'g0', ':': 'g1', '+': 'g2', 'x': 'g3', '#': 'g4', 'bloco': 'g5'}[nome]
        out.append(f'<path id="{ident}" d="{"".join(d)}"/>')
    return ''.join(out)


def losango(cx, cy, r, cor, dentro=''):
    """Moldura em losango em volta do icone, como nos itens do menu do jogo."""
    return (f'<path d="M{cx:g} {cy - r:g} L{cx + r:g} {cy:g} L{cx:g} {cy + r:g} L{cx - r:g} {cy:g} Z" '
            f'fill="none" stroke="{cor}" stroke-width="1.2"/>{dentro}')
