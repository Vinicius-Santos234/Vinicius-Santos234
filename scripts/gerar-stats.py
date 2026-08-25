# -*- coding: utf-8 -*-
"""Gera stats.svg — cartao de estatisticas do perfil, no visual do terminal.

Sem dependencia de servico de terceiros: le a API do GitHub e desenha o SVG.
Com GITHUB_TOKEN no ambiente usa o GraphQL (commits do ano + sequencia de dias);
sem token cai para a API REST publica (commits publicos via search).

Uso:  python scripts/gerar-stats.py [usuario]
"""
import io, json, os, sys, urllib.request, urllib.error
from datetime import datetime, timezone

USER = sys.argv[1] if len(sys.argv) > 1 else "Vinicius-Santos234"
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stats.svg")

CORES = {
    "JavaScript": "#f1e05a", "Python": "#3572A5", "TypeScript": "#3178c6",
    "HTML": "#e34c26", "CSS": "#563d7c", "SCSS": "#c6538c", "Dart": "#00B4AB",
    "PowerShell": "#012456", "Shell": "#89e051", "Batchfile": "#C1F12E",
    "Java": "#b07219", "C#": "#178600", "C++": "#f34b7d", "C": "#555555",
    "Kotlin": "#A97BFF", "Ruby": "#701516", "PHP": "#4F5D95", "Go": "#00ADD8",
    "Rust": "#dea584", "Swift": "#F05138", "Vue": "#41b883",
    "Jupyter Notebook": "#DA5B0B", "Makefile": "#427819", "Dockerfile": "#384d54",
}
OUTROS = "#6e7681"


def api(url, graphql=None):
    hdr = {"User-Agent": "perfil-stats", "Accept": "application/vnd.github+json"}
    if TOKEN:
        hdr["Authorization"] = "Bearer " + TOKEN
    data = None
    if graphql is not None:
        data = json.dumps({"query": graphql}).encode()
        hdr["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdr)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def coletar():
    d = {"login": USER}
    u = api("https://api.github.com/users/%s" % USER)
    d["seguidores"] = u.get("followers", 0)
    d["desde"] = u.get("created_at", "")[:4]

    repos, page = [], 1
    while True:
        lote = api("https://api.github.com/users/%s/repos?per_page=100&page=%d" % (USER, page))
        repos.extend(lote)
        if len(lote) < 100:
            break
        page += 1
    proprios = [r for r in repos if not r.get("fork")]
    d["repos"] = len(proprios)
    d["estrelas"] = sum(r.get("stargazers_count", 0) for r in proprios)

    bytes_por_lang = {}
    for r in proprios:
        try:
            for lang, n in api(r["languages_url"]).items():
                bytes_por_lang[lang] = bytes_por_lang.get(lang, 0) + n
        except urllib.error.HTTPError:
            pass
    d["langs"] = bytes_por_lang

    d["commits"] = None
    d["commits_rotulo"] = "commits"
    d["sequencia"] = None
    if TOKEN:
        q = ('{ user(login: "%s") { contributionsCollection {'
             ' totalCommitContributions'
             ' contributionCalendar { weeks { contributionDays { date contributionCount } } }'
             ' } } }') % USER
        try:
            g = api("https://api.github.com/graphql", graphql=q)
            cc = g["data"]["user"]["contributionsCollection"]
            d["commits"] = cc["totalCommitContributions"]
            d["commits_rotulo"] = "commits (12 meses)"
            dias = [dia for semana in cc["contributionCalendar"]["weeks"]
                    for dia in semana["contributionDays"]]
            dias.sort(key=lambda x: x["date"])
            hoje = datetime.now(timezone.utc).date().isoformat()
            if dias and dias[-1]["date"] == hoje and dias[-1]["contributionCount"] == 0:
                dias = dias[:-1]          # o dia de hoje ainda nao acabou
            seq = 0
            for dia in reversed(dias):
                if dia["contributionCount"] > 0:
                    seq += 1
                else:
                    break
            d["sequencia"] = seq
        except Exception as e:
            sys.stderr.write("graphql falhou: %r\n" % (e,))
    if d["commits"] is None:
        try:
            s = api("https://api.github.com/search/commits?q=author:%s&per_page=1" % USER)
            d["commits"] = s.get("total_count", 0)
            d["commits_rotulo"] = "commits públicos"
        except Exception as e:
            sys.stderr.write("search falhou: %r\n" % (e,))
            d["commits"] = 0
    return d


def top_langs(langs, n=6):
    total = sum(langs.values()) or 1
    itens = sorted(langs.items(), key=lambda kv: -kv[1])
    principais = [(k, v / total * 100) for k, v in itens[:n] if v / total * 100 >= 1.0]
    resto = 100 - sum(p for _, p in principais)
    if resto >= 1.0:
        principais.append(("outros", resto))
    return principais


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def desenhar(d):
    W = 804.0
    PADX = 38.0
    TOP = 40.0
    FS = 15.0
    MONO = ("font-family:ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,"
            "'DejaVu Sans Mono',monospace")

    langs = top_langs(d["langs"])
    y = TOP + 34
    body = ['<text x="%g" y="%g" class="m" xml:space="preserve">'
            '<tspan class="u">visitante@github</tspan><tspan class="d">:</tspan>'
            '<tspan class="p">~</tspan><tspan class="d">$ </tspan>'
            '<tspan class="c">gh stats </tspan><tspan class="f">--user %s</tspan></text>'
            % (PADX, y, esc(d["login"]))]

    # sem token nao ha calendario de contribuicoes: mostra estrelas no lugar da sequencia
    if d["sequencia"] is not None:
        quarta = ("sequência atual",
                  "%d dia%s" % (d["sequencia"], "" if d["sequencia"] == 1 else "s"))
    elif d["estrelas"] > 0:
        quarta = ("estrelas recebidas", d["estrelas"])
    else:
        quarta = ("no GitHub desde", d.get("desde") or "--")
    metricas = [
        ("repositórios próprios", d["repos"]),
        (d["commits_rotulo"], d["commits"]),
        ("seguidores", d["seguidores"]),
        quarta,
    ]
    y += 40
    colx = [PADX, PADX + 380]
    for i, (rot, val) in enumerate(metricas):
        cx = colx[i % 2]
        cy = y + (i // 2) * 30
        body.append('<text x="%g" y="%g" class="m rot">%s</text>' % (cx, cy, esc(rot)))
        body.append('<text x="%g" y="%g" class="m val v%d" text-anchor="end">%s</text>'
                    % (cx + 330, cy, i, esc(val)))

    y += 30 + 46
    body.append('<text x="%g" y="%g" class="m rot">linguagens '
                '<tspan class="d">(bytes de código, sem forks)</tspan></text>' % (PADX, y))
    y += 28
    CEL, GAPB, NCEL = 12.0, 2.0, 34
    largura_barra = NCEL * CEL
    for i, (nome, pct) in enumerate(langs):
        ly = y + i * 26
        cor = CORES.get(nome, OUTROS)
        body.append('<text x="%g" y="%g" class="m nome">%s</text>' % (PADX, ly, esc(nome)))
        bx = PADX + 172
        cheias = max(1, int(round(pct / 100 * NCEL)))
        celulas = []
        for c in range(NCEL):
            preenchida = c < cheias
            celulas.append('<rect x="%g" y="%g" width="%g" height="12" fill="%s" opacity="%s"/>'
                           % (bx + c * CEL, ly - 11, CEL - GAPB,
                              cor if preenchida else "#30363d", "1" if preenchida else ".55"))
        body.append('<g class="bar b%d" style="transform-origin:%gpx %gpx">%s</g>'
                    % (i, bx, ly, "".join(celulas)))
        body.append('<text x="%g" y="%g" class="m pct" text-anchor="end">%.1f%%</text>'
                    % (bx + largura_barra + 66, ly, pct))

    y += len(langs) * 26 + 18
    agora = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    body.append('<text x="%g" y="%g" class="m dt">atualizado em %s '
                '<tspan class="d">// gerado por GitHub Actions, sem serviço externo</tspan></text>'
                % (PADX, y, agora))
    H = y + 30

    css = [
        ".m{%s;font-size:%gpx;letter-spacing:.3px}" % (MONO, FS),
        ".u{fill:#7ee787}.d{fill:#6e7681}.p{fill:#79c0ff}.c{fill:#e6edf3}.f{fill:#d2a8ff}",
        ".rot{fill:#8b949e}.nome{fill:#c9d1d9}.pct{fill:#8b949e;font-size:13px}",
        ".val{fill:#e5484d;font-weight:700;animation:surge .5s ease-out both}",
        ".dt{fill:#6e7681;font-size:12px}",
        ".bar{animation:cresce .9s cubic-bezier(.2,.8,.25,1) both}",
        "@keyframes cresce{from{transform:scaleX(0)}to{transform:scaleX(1)}}",
        "@keyframes surge{from{opacity:0}to{opacity:1}}",
    ]
    for i in range(len(langs)):
        css.append(".b%d{animation-delay:%.2fs}" % (i, 0.35 + i * 0.09))
    for i in range(4):
        css.append(".v%d{animation-delay:%.2fs}" % (i, 0.12 + i * 0.08))

    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
           'role="img" aria-label="Estatisticas do GitHub de %s">\n'
           '<title>gh stats --user %s</title>\n<style>%s</style>\n'
           '<rect x="0.5" y="0.5" width="%d" height="%d" rx="12" fill="#0b0e14" stroke="#21262d"/>\n'
           '<path d="M0.5 12.5a12 12 0 0 1 12-12h%da12 12 0 0 1 12 12v%dH0.5z" fill="#11151c"/>\n'
           '<line x1="0.5" y1="%g" x2="%g" y2="%g" stroke="#21262d"/>\n'
           '<circle cx="22" cy="20" r="5.5" fill="#ff5f57"/>'
           '<circle cx="42" cy="20" r="5.5" fill="#febc2e"/>'
           '<circle cx="62" cy="20" r="5.5" fill="#28c840"/>\n'
           '<text x="%g" y="25" text-anchor="middle" class="m" '
           'style="font-size:12.5px;fill:#6e7681">%s &#8212; gh stats</text>\n%s\n</svg>\n'
           % (int(W), int(H), int(W), int(H), esc(USER), esc(USER), "".join(css),
              int(W) - 1, int(H) - 1, int(W) - 25, int(TOP) - 12,
              TOP + 0.5, W - 0.5, TOP + 0.5, W / 2, esc(USER.lower()), "".join(body)))
    io.open(OUT, "w", encoding="utf-8").write(svg)
    return int(H)


if __name__ == "__main__":
    dados = coletar()
    altura = desenhar(dados)
    sys.stdout.write("stats.svg gerado (804x%d) | repos=%s commits=%s seguidores=%s seq=%s\n"
                     % (altura, dados["repos"], dados["commits"],
                        dados["seguidores"], dados["sequencia"]))
