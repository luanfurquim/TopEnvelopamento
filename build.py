#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.py — transforma o bundle do construtor em HTML estatico rastreavel.

POR QUE ISSO EXISTE
-------------------
O `index.html` gerado pelo construtor e um bundle: o HTML da pagina viaja
como string JSON dentro de <script type="__bundler/template">, e o JavaScript
monta o DOM no navegador. Funciona para humano e e invisivel para robo — sem
executar JS a pagina tem 0 secao, 0 imagem e 0 botao de WhatsApp.

Este script le esse bundle e escreve um `index.html` de verdade, com o mesmo
resultado visual, sem depender de JavaScript para existir.

PIPELINE
--------
    Top Envelopamento PPF.dc.html   (edicao no construtor)
        -> index.bundle.html        (saida compilada do construtor)
        -> python build.py          (ESTE SCRIPT)
        -> index.html               (estatico, e o que vai pro ar)

Rodar de novo depois de qualquer reexportacao do construtor.

USO
---
    python build.py                 # build completo
    python build.py --sem-imagens   # pula a otimizacao (mais rapido)
"""

import base64
import gzip
import html as H
import json
import os
import re
import shutil
import sys
import zlib

RAIZ = os.path.dirname(os.path.abspath(__file__))

# O bundle de entrada. Na primeira execucao ainda e o proprio index.html;
# depois disso o script preserva uma copia como index.bundle.html.
ENTRADA_BUNDLE = "index.bundle.html"
ENTRADA_FALLBACK = "index.html"
SAIDA = "index.html"

DIR_IMG_FONTE = "img"
DIR_IMG_SAIDA = os.path.join("assets", "img")
DIR_FONTES = os.path.join("assets", "fonts")

# Os mesmos caminhos como URL (sempre com barra normal, mesmo no Windows)
URL_IMG = "/assets/img"
URL_FONTES = "/assets/fonts"

# Largura maxima real de cada imagem na tela, medida no layout.
# Serve para nao servir 1086px onde cabem 470.
LARGURA_ALVO = {
    "hero.jpg": 1920,      # fundo da primeira dobra, ocupa a tela inteira
    "porsche.jpg": 1600,   # imagem larga de secao
    "_carrossel": 940,     # cartoes de ate 470px, servidos em 2x
    "_padrao": 1200,
}
CARROSSEL = {f"{i:02d}.jpg" for i in range(1, 12)}
QUALIDADE_JPG = 82
QUALIDADE_WEBP = 78

# A ordem das secoes no HTML final. Cada numero e a posicao da secao no
# template original. Mexer aqui reordena a pagina inteira.
# Decidido em 14/08/2026 — ver 05-carrossel-decisao.md no diagnostico.
#
#   posicao no template            ->  posicao final
#   1  Hero                            1
#   2  O que e PPF                     2
#   7  Projetos (carrossel)            3   <- sobe da dobra 10,3 para a 2,1
#   4  Do que protege                  4
#   6  Autoridade / quem entende       5
#   3  QuadFilm (tecnico, 3,1 dobras)  6   <- desce, vem depois da prova
#   5  Como funciona a aplicacao       7
#   8  FAQ                             8
#   9  Onde estamos                    9
#   10 CTA final                       10
#
# ORDEM_SECOES = None mantem a ordem do template.
ORDEM_SECOES = [1, 2, 7, 4, 6, 3, 5, 8, 9, 10]


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------- bundle

def descomprime(item):
    """Os recursos do bundle vem em base64, alguns com gzip por cima."""
    bruto = base64.b64decode(item["data"])
    if not item.get("compressed"):
        return bruto
    for tentativa in (gzip.decompress,
                      zlib.decompress,
                      lambda b: zlib.decompress(b, -15)):
        try:
            return tentativa(bruto)
        except Exception:
            continue
    raise RuntimeError("nao consegui descomprimir um recurso do bundle")


def le_bundle():
    caminho = os.path.join(RAIZ, ENTRADA_BUNDLE)
    if not os.path.exists(caminho):
        caminho = os.path.join(RAIZ, ENTRADA_FALLBACK)
        conteudo = open(caminho, "rb").read().decode("utf-8")
        if "__bundler/template" not in conteudo:
            sys.exit(
                f"ERRO: {ENTRADA_FALLBACK} nao e um bundle do construtor e\n"
                f"      {ENTRADA_BUNDLE} nao existe. Nada a fazer."
            )
        # primeira execucao: preserva o bundle antes de sobrescrever a saida
        shutil.copy2(caminho, os.path.join(RAIZ, ENTRADA_BUNDLE))
        log(f"  bundle preservado como {ENTRADA_BUNDLE}")
    conteudo = open(caminho, "rb").read().decode("utf-8")

    manifest = json.loads(
        re.search(r'<script type="__bundler/manifest">(.*?)</script>',
                  conteudo, re.S).group(1))
    template = json.loads(
        re.search(r'<script type="__bundler/template">(.*?)</script>',
                  conteudo, re.S).group(1))
    return conteudo, manifest, template


# ---------------------------------------------------------------- recursos

def escreve_fontes(manifest):
    """As 7 woff2 vem embutidas em base64. Viram arquivo."""
    os.makedirs(os.path.join(RAIZ, DIR_FONTES), exist_ok=True)
    mapa = {}
    for uuid, item in manifest.items():
        if item.get("mime") != "font/woff2":
            continue
        dados = descomprime(item)
        nome = f"{uuid[:8]}.woff2"
        with open(os.path.join(RAIZ, DIR_FONTES, nome), "wb") as f:
            f.write(dados)
        mapa[uuid] = f"/{DIR_FONTES}/{nome}".replace("\\", "/")
    log(f"  {len(mapa)} fontes escritas em {DIR_FONTES}/")
    return mapa


def escreve_logo(manifest):
    """O logo e um SVG embutido; vira arquivo em assets/."""
    for uuid, item in manifest.items():
        if item.get("mime") != "image/svg+xml":
            continue
        dados = descomprime(item)
        destino = os.path.join(RAIZ, "assets", "logo-top.svg")
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "wb") as f:
            f.write(dados)
        log("  logo escrito em assets/logo-top.svg")
        return {uuid: "/assets/logo-top.svg"}
    return {}


ARQUIVO_MAPA = "build-imagens.json"


def mapeia_imagens(manifest):
    """
    Casa cada UUID de imagem do bundle com o arquivo de nome legivel em img/.

    O construtor exporta as imagens com nome de UUID. Para o HTML final citar
    `hero.jpg` em vez de `fb40db09-...`, e preciso saber qual e qual.

    Duas fontes, nesta ordem:
      1. `img-bundle/<uuid>.jpg`, se a pasta existir — casa por conteudo (md5)
      2. `build-imagens.json`, o mapa gravado por uma execucao anterior

    A segunda existe para que `img-bundle/` possa ser apagada do repositorio:
    ela e copia byte a byte de `img/` e so servia para esta correspondencia.
    """
    import hashlib

    caminho_mapa = os.path.join(RAIZ, ARQUIVO_MAPA)
    uuids_img = [u for u, i in manifest.items()
                 if (i.get("mime") or "").startswith("image/jpeg")]

    dir_bundle = os.path.join(RAIZ, "img-bundle")
    if os.path.isdir(dir_bundle):
        por_hash = {}
        for nome in os.listdir(os.path.join(RAIZ, DIR_IMG_FONTE)):
            caminho = os.path.join(RAIZ, DIR_IMG_FONTE, nome)
            if os.path.isfile(caminho):
                por_hash[hashlib.md5(open(caminho, "rb").read()).hexdigest()] = nome

        mapa, faltando = {}, []
        for uuid in uuids_img:
            origem = os.path.join(dir_bundle, f"{uuid}.jpg")
            if not os.path.exists(origem):
                faltando.append(uuid)
                continue
            digest = hashlib.md5(open(origem, "rb").read()).hexdigest()
            nome = por_hash.get(digest)
            if not nome:                       # imagem nova, ainda sem nome em img/
                nome = f"{uuid[:8]}.jpg"
                shutil.copy2(origem, os.path.join(RAIZ, DIR_IMG_FONTE, nome))
            mapa[uuid] = nome

        if faltando:
            log(f"  AVISO: {len(faltando)} imagens do manifest sem arquivo em img-bundle/")

        with open(caminho_mapa, "w", encoding="utf-8") as f:
            json.dump(mapa, f, indent=2, ensure_ascii=False, sort_keys=True)
        log(f"  {len(mapa)} imagens casadas por conteudo (mapa gravado)")
        return mapa

    # sem img-bundle: usa o mapa gravado
    if not os.path.exists(caminho_mapa):
        sys.exit(
            f"ERRO: nao existe nem a pasta img-bundle/ nem o {ARQUIVO_MAPA}.\n"
            "      Sem um dos dois nao da para saber que UUID e que foto.\n"
            "      Restaure img-bundle/ do historico do git e rode de novo."
        )

    mapa = json.load(open(caminho_mapa, encoding="utf-8"))
    desconhecidos = [u for u in uuids_img if u not in mapa]
    if desconhecidos:
        sys.exit(
            f"ERRO: {len(desconhecidos)} imagens do bundle nao estao no {ARQUIVO_MAPA}.\n"
            "      O construtor gerou UUIDs novos (fotos trocadas?).\n"
            "      Restaure img-bundle/ do historico do git, rode uma vez para\n"
            f"      regravar o {ARQUIVO_MAPA}, e apague a pasta de novo."
        )

    ausentes = [n for n in mapa.values()
                if not os.path.exists(os.path.join(RAIZ, DIR_IMG_FONTE, n))]
    if ausentes:
        sys.exit(f"ERRO: faltam em img/: {', '.join(ausentes)}")

    log(f"  {len(mapa)} imagens casadas pelo {ARQUIVO_MAPA}")
    return mapa


def otimiza_imagens(mapa_img, pular=False):
    """
    Reduz cada imagem para a largura em que ela realmente aparece e gera
    WebP ao lado. Devolve as dimensoes finais, para preencher width/height
    no HTML e acabar com o salto de layout.
    """
    destino = os.path.join(RAIZ, DIR_IMG_SAIDA)
    os.makedirs(destino, exist_ok=True)

    try:
        from PIL import Image
    except ImportError:
        if not pular:
            log("  AVISO: Pillow nao instalado (pip install Pillow).")
            log("         Copiando as imagens sem otimizar.")
        pular = True

    dims = {}
    antes = depois = 0

    for uuid, nome in sorted(mapa_img.items(), key=lambda x: x[1]):
        origem = os.path.join(RAIZ, DIR_IMG_FONTE, nome)
        antes += os.path.getsize(origem)

        if pular:
            shutil.copy2(origem, os.path.join(destino, nome))
            try:
                from PIL import Image as _I
                with _I.open(origem) as im:
                    dims[nome] = im.size
            except Exception:
                dims[nome] = (None, None)
            depois += os.path.getsize(os.path.join(destino, nome))
            continue

        alvo = (LARGURA_ALVO.get(nome)
                or (LARGURA_ALVO["_carrossel"] if nome in CARROSSEL
                    else LARGURA_ALVO["_padrao"]))

        with Image.open(origem) as im:
            im = im.convert("RGB")
            if im.width > alvo:
                altura = round(im.height * alvo / im.width)
                im = im.resize((alvo, altura), Image.LANCZOS)
            dims[nome] = im.size

            saida_jpg = os.path.join(destino, nome)
            im.save(saida_jpg, "JPEG", quality=QUALIDADE_JPG,
                    optimize=True, progressive=True)
            im.save(os.path.splitext(saida_jpg)[0] + ".webp", "WEBP",
                    quality=QUALIDADE_WEBP, method=6)

        depois += os.path.getsize(os.path.join(destino, nome))

    if antes:
        log(f"  imagens: {antes/1048576:.2f} MB -> {depois/1048576:.2f} MB "
            f"({100*(1-depois/antes):.0f}% menor), + WebP ao lado")
    return dims


# ---------------------------------------------------------------- HTML

WA_NUMERO = "5517991883704"
WA_MSG = "Oi! Vim pelo site e quero um orçamento de PPF. Meu carro é um :"


def link_whatsapp():
    from urllib.parse import quote
    return f"https://wa.me/{WA_NUMERO}?text={quote(WA_MSG, safe='')}"


def resolve_placeholders(tpl):
    """
    O template usa {{ }} para valores que o React resolvia em tempo de
    execucao. Como nao havera React, resolvemos aqui.
    """
    tpl = tpl.replace("{{ waLink }}", link_whatsapp())
    # os refs do React viram ganchos de CSS
    tpl = re.sub(r'ref="\{\{\s*rowA\s*\}\}"', 'class="marquee-track" data-marquee="a"', tpl)
    tpl = re.sub(r'ref="\{\{\s*rowB\s*\}\}"', 'class="marquee-track" data-marquee="b"', tpl)
    return tpl


def resolve_condicionais(tpl):
    """<sc-if value="{{ showGallery }}"> — as duas condicoes sao true."""
    tpl = re.sub(r'<sc-if[^>]*>', '', tpl)
    tpl = tpl.replace('</sc-if>', '')
    return tpl


def troca_imagens(tpl, mapa_img, mapa_extra, dims):
    """
    src="<uuid>"  ->  <picture><source ...webp><img src="/assets/img/hero.jpg"
                      width=".." height=".." decoding="async"></picture>

    O WebP corta cerca de metade do peso. O <picture> leva
    `display:contents` no CSS, entao nao cria caixa e nao mexe no layout —
    as imagens continuam com o mesmo position:absolute de antes.
    """
    trocadas = [0]
    primeira = [True]

    def repl(m):
        tag, uuid = m.group(0), m.group(1)

        if uuid in mapa_extra:                      # logo SVG, sem WebP
            trocadas[0] += 1
            return tag.replace(f'src="{uuid}"', f'src="{mapa_extra[uuid]}"')

        nome = mapa_img.get(uuid)
        if not nome:
            return tag

        trocadas[0] += 1
        largura, altura = dims.get(nome, (None, None))
        novo = tag.replace(f'src="{uuid}"', f'src="{URL_IMG}/{nome}"')

        if largura and 'width=' not in novo:
            novo = novo.replace("<img", f'<img width="{largura}" height="{altura}"', 1)
        if "decoding=" not in novo:
            novo = novo.replace("<img", '<img decoding="async"', 1)

        # a imagem da primeira dobra e o LCP: prioridade alta e nunca lazy
        if primeira[0]:
            novo = novo.replace(' loading="lazy"', '')
            novo = novo.replace("<img", '<img fetchpriority="high"', 1)
            primeira[0] = False
        elif 'loading=' not in novo:
            novo = novo.replace("<img", '<img loading="lazy"', 1)

        webp = f"{URL_IMG}/{os.path.splitext(nome)[0]}.webp"
        return (f'<picture><source srcset="{webp}" type="image/webp">'
                f'{novo}</picture>')

    tpl = re.sub(r'<img[^>]*src="([0-9a-f-]{36})"[^>]*>', repl, tpl)
    log(f"  {trocadas[0]} imagens apontando para arquivo real (com WebP)")
    return tpl


def troca_fontes(css, mapa_fontes):
    for uuid, caminho in mapa_fontes.items():
        css = css.replace(f'url("{uuid}")', f'url("{caminho}")')
        css = css.replace(f"url('{uuid}')", f"url('{caminho}')")
        css = css.replace(f"url({uuid})", f"url({caminho})")
    return css


CSS_EXTRA = """
/* <picture> nao pode criar caixa: as imagens dentro dele continuam com o
   mesmo position:absolute de antes e o layout fica identico. */
picture { display: contents; }

/* ---- menu mobile ----
   Antes isto era injetado por um script que rodava a cada 100ms, 150 vezes,
   criando o botao e o dropdown no navegador. Agora o markup ja nasce pronto
   e sobra so o clique. Mesmo resultado visual, sem o laco. */
html { overflow-x: hidden; overflow-x: clip; }
@media (max-width: 768px) {
  header nav a[href^="#"] { display: none !important; }
  #mb-burger { display: inline-flex !important; align-items: center;
    justify-content: center; width: 42px; height: 42px; border: 1px solid #262626;
    border-radius: 10px; background: transparent; cursor: pointer;
    margin-left: 10px; flex: 0 0 auto; }
  #mb-burger span { position: relative; width: 20px; height: 2px;
    background: #f4f2ee; display: block; transition: .2s; }
  #mb-burger span::before, #mb-burger span::after { content: ""; position: absolute;
    left: 0; width: 20px; height: 2px; background: #f4f2ee; transition: .2s; }
  #mb-burger span::before { top: -6px; }
  #mb-burger span::after  { top: 6px; }
  #mb-burger.open span { background: transparent; }
  #mb-burger.open span::before { top: 0; transform: rotate(45deg); }
  #mb-burger.open span::after  { top: 0; transform: rotate(-45deg); }
  #mb-dd { display: none; position: absolute; top: 100%; left: 0; right: 0;
    background: #0a0a0a; border-top: 1px solid #262626; padding: 8px 20px 16px;
    flex-direction: column; z-index: 60; }
  #mb-dd.open { display: flex; }
  #mb-dd a { color: #f4f2ee; text-decoration: none; padding: 14px 4px;
    font-size: 15px; letter-spacing: .06em; text-transform: uppercase;
    border-bottom: 1px solid #1c1c1c; }
  #mb-dd a:last-child { border-bottom: none; }
}
@media (min-width: 769px) { #mb-burger, #mb-dd { display: none !important; } }

/* ---- marquee em CSS puro (antes era requestAnimationFrame no React) ---- */
@keyframes marquee-esq { from { transform: translate3d(0,0,0); }
                         to   { transform: translate3d(-50%,0,0); } }
@keyframes marquee-dir { from { transform: translate3d(-50%,0,0); }
                         to   { transform: translate3d(0,0,0); } }
.marquee-track { animation-timing-function: linear;
                 animation-iteration-count: infinite; }
.marquee-track[data-marquee="a"] { animation-name: marquee-esq; animation-duration: 140s; }
.marquee-track[data-marquee="b"] { animation-name: marquee-dir; animation-duration: 180s; }

/* Para quando o visitante quer olhar. No mouse basta o :hover; no celular
   quem segura a pausa e a classe .parado, posta pelo JS no toque.
   Sem isso, quem tem carro de R$ 150 mil nao consegue parar numa foto para
   procurar um parecido com o dele. */
.marquee-track:hover,
.marquee-track.parado { animation-play-state: paused; }

/* ---- entrada suave: so acontece se o JS rodar ----
   Sem JS o conteudo ja nasce visivel. Era o contrario antes: o React
   zerava a opacidade de tudo e revelava depois. */
.js-reveal [data-reveal] { opacity: 0; transform: translate3d(0,16px,0);
    transition: opacity .8s cubic-bezier(.22,.61,.36,1),
                transform .8s cubic-bezier(.22,.61,.36,1); }
.js-reveal [data-reveal].visivel { opacity: 1; transform: none; }

@media (prefers-reduced-motion: reduce) {
  .marquee-track { animation: none; }
  .js-reveal [data-reveal] { opacity: 1; transform: none; transition: none; }
}
"""

JS_EXTRA = """
/* Pausa o carrossel enquanto o dedo esta encostado. No desktop o :hover do
   CSS ja resolve; isto e para o celular, onde nao existe hover. */
(function () {
  var trilhos = document.querySelectorAll('.marquee-track');
  if (!trilhos.length) return;
  var bloco = trilhos[0].closest('section');
  if (!bloco) return;

  function pausa()  { trilhos.forEach(function (t) { t.classList.add('parado'); }); }
  function retoma() { trilhos.forEach(function (t) { t.classList.remove('parado'); }); }

  bloco.addEventListener('touchstart', pausa,  { passive: true });
  bloco.addEventListener('touchend',   retoma, { passive: true });
  bloco.addEventListener('touchcancel', retoma, { passive: true });
})();

/* Abre e fecha o menu mobile. O markup ja veio pronto no HTML. */
document.addEventListener('click', function (e) {
  var t = e.target;
  if (!t || !t.closest) return;
  var dd = document.getElementById('mb-dd'), bg = document.getElementById('mb-burger');
  if (t.closest('#mb-burger')) {
    if (dd) dd.classList.toggle('open');
    if (bg) bg.classList.toggle('open');
  } else if (t.closest('#mb-dd a')) {
    if (dd) dd.classList.remove('open');
    if (bg) bg.classList.remove('open');
  }
});

/* Entrada suave das secoes. Progressivo: sem JS, tudo ja esta visivel. */
(function () {
  var reduz = window.matchMedia &&
              window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduz || !('IntersectionObserver' in window)) return;

  var alvos = [];
  document.querySelectorAll('section > *, footer > *').forEach(function (el) {
    if (el.tagName === 'IMG') return;
    if (el.getAttribute('aria-hidden') === 'true') return;
    if (el.style && el.style.position === 'absolute') return;
    var filhos = el.style && el.style.maxWidth === '1280px'
               ? Array.prototype.slice.call(el.children) : [el];
    filhos.forEach(function (f) { f.setAttribute('data-reveal', ''); alvos.push(f); });
  });
  if (!alvos.length) return;

  document.documentElement.classList.add('js-reveal');

  var io = new IntersectionObserver(function (ents, obs) {
    ents.filter(function (e) { return e.isIntersecting; })
        .forEach(function (e, i) {
          e.target.style.transitionDelay = Math.min(i, 4) * 90 + 'ms';
          e.target.classList.add('visivel');
          obs.unobserve(e.target);
        });
  }, { threshold: 0.08, rootMargin: '0px 0px -8% 0px' });

  alvos.forEach(function (el) { io.observe(el); });

  /* a primeira dobra nao espera scroll */
  var primeira = document.querySelector('section');
  if (primeira) {
    Array.prototype.slice.call(primeira.querySelectorAll('[data-reveal]'))
      .forEach(function (el, i) {
        setTimeout(function () { el.classList.add('visivel'); }, 80 + i * 110);
      });
  }
})();
"""


def injeta_menu_mobile(corpo):
    """
    Escreve no HTML o botao de hamburguer e o dropdown que antes eram criados
    por JavaScript. Os links sao os mesmos do <nav>, clonados.
    """
    cab = re.search(r'<header[\s>].*?</header>', corpo, re.S)
    if not cab:
        log("  AVISO: nao achei o <header>; menu mobile nao foi injetado")
        return corpo

    bloco = cab.group(0)

    # so os links de dentro do <nav> — o logo tambem e uma ancora e nao entra
    nav = re.search(r'<nav[\s>].*?</nav>', bloco, re.S)
    escopo = nav.group(0) if nav else bloco

    links = [(href, re.sub(r'<[^>]+>', '', texto).strip())
             for href, texto in re.findall(
                 r'<a[^>]*href="(#[^"]*)"[^>]*>(.*?)</a>', escopo, re.S)]
    links = [(h, t) for h, t in links if t and h != '#']

    if not links:
        log("  AVISO: nenhum link de ancora dentro do <nav>")
        return corpo

    botao = ('<button id="mb-burger" type="button" aria-label="Menu" '
             'aria-expanded="false"><span></span></button>')
    itens = "".join(f'<a href="{href}">{texto}</a>' for href, texto in links)
    dropdown = f'<div id="mb-dd">{itens}</div>'

    novo = bloco
    ult_nav = novo.rfind('</nav>')
    if ult_nav != -1:
        novo = novo[:ult_nav] + botao + novo[ult_nav:]
    else:
        log("  AVISO: <header> sem <nav>; botao nao foi inserido")
    novo = novo[:novo.rfind('</header>')] + dropdown + novo[novo.rfind('</header>'):]

    log(f"  menu mobile no HTML: 1 botao + dropdown com {len(links)} links")
    return corpo.replace(bloco, novo, 1)


def reordena_secoes(corpo, ordem):
    """Reordena as <section> de primeiro nivel. ordem = lista de indices 1-based."""
    if not ordem:
        return corpo

    posicoes = []
    profundidade = 0
    for m in re.finditer(r'<(/?)section[\s>]', corpo):
        if m.group(1):
            profundidade -= 1
            if profundidade == 0:
                fim = corpo.find('>', corpo.find('</section', m.start())) + 1
                posicoes[-1] = (posicoes[-1][0], fim)
        else:
            if profundidade == 0:
                posicoes.append((m.start(), None))
            profundidade += 1

    blocos = [corpo[a:b] for a, b in posicoes]
    if sorted(ordem) != list(range(1, len(blocos) + 1)):
        sys.exit(f"ERRO: ORDEM_SECOES precisa listar 1..{len(blocos)} exatamente uma vez")

    novos = [blocos[i - 1] for i in ordem]
    resultado, ultimo = [], 0
    for (a, b), novo in zip(posicoes, novos):
        resultado.append(corpo[ultimo:a])
        resultado.append(novo)
        ultimo = b
    resultado.append(corpo[ultimo:])
    log(f"  secoes reordenadas: {ordem}")
    return "".join(resultado)


def monta_html(tpl, mapa_fontes):
    """Separa <helmet> (vira <head>) do resto (vira <body>) e monta o documento."""
    m = re.search(r'<helmet>(.*?)</helmet>', tpl, re.S)
    if not m:
        sys.exit("ERRO: nao achei o bloco <helmet> no template")
    cabeca = m.group(1)

    ini = tpl.find('<x-dc>')
    fim = tpl.rfind('</x-dc>')
    corpo = tpl[ini + len('<x-dc>'):fim]
    corpo = corpo.replace(m.group(0), '')            # tira o helmet do corpo

    # o componente React nao vai junto — era so comportamento
    corpo = re.sub(r'<script type="text/x-dc"[^>]*>.*?</script>', '', corpo, flags=re.S)

    corpo = injeta_menu_mobile(corpo)
    corpo = reordena_secoes(corpo, ORDEM_SECOES)

    cabeca = troca_fontes(cabeca, mapa_fontes)
    cabeca = cabeca.replace('</style>', CSS_EXTRA + '</style>', 1) \
        if '</style>' in cabeca else cabeca + f'<style>{CSS_EXTRA}</style>'

    return (
        '<!DOCTYPE html>\n'
        '<html lang="pt-BR">\n<head>\n'
        '<meta charset="utf-8">\n'
        + cabeca.strip() + '\n'
        '</head>\n<body>\n'
        + corpo.strip() + '\n'
        f'<script>{JS_EXTRA}</script>\n'
        '</body>\n</html>\n'
    )


# ---------------------------------------------------------------- conferencia

def confere(caminho):
    """Os mesmos testes que expuseram o problema original."""
    doc = open(caminho, encoding='utf-8').read()
    blocos = [(m.start(), doc.find('</script>', m.start()))
              for m in re.finditer(r'<script', doc)]

    def fora_de_script(i):
        return not any(a <= i <= b for a, b in blocos)

    def conta(tag):
        return sum(1 for m in re.finditer(re.escape(tag), doc)
                   if fora_de_script(m.start()))

    sem_js = re.sub(r'<script.*?</script>', '', doc, flags=re.S)
    texto = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', sem_js)).strip()

    checagens = [
        ("secoes em HTML real",        conta('<section'), 10, 'igual'),
        ("titulos h2 em HTML real",    conta('<h2'),       9, 'igual'),
        ("imagens em HTML real",       conta('<img'),     28, 'igual'),
        ("links de WhatsApp",          conta('wa.me'),     6, 'igual'),
        ("texto visivel sem JS",       len(texto),      4000, 'min'),
        ("tag do Google Ads",          doc.count('AW-16763500925'), 1, 'min'),
        ("rotulo de conversao",        doc.count('Lr_VCIP2st8cEP3yurk-'), 1, 'min'),
        ("schema AutoBodyShop",        doc.count('AutoBodyShop'), 1, 'min'),
        ("schema FAQPage",             doc.count('FAQPage'), 1, 'min'),
        ("lang=pt-BR no <html>",       doc.count('<html lang="pt-BR"'), 1, 'min'),
        ("uuid sobrando no HTML",      len(re.findall(r'src="[0-9a-f-]{36}"', doc)), 0, 'igual'),
        ("placeholder {{ }} sobrando", len(re.findall(r'\{\{[^}]+\}\}', doc)), 0, 'igual'),
    ]

    log("")
    log("  CONFERENCIA")
    ok = True
    for nome, valor, esperado, modo in checagens:
        passou = valor == esperado if modo == 'igual' else valor >= esperado
        ok = ok and passou
        alvo = f"= {esperado}" if modo == 'igual' else f">= {esperado}"
        log(f"    [{'OK' if passou else '--'}] {nome:<28} {valor:>6}  (esperado {alvo})")

    peso = os.path.getsize(caminho)
    log(f"    [--] tamanho do index.html      {peso/1024:>5.0f} KB")
    return ok


# ---------------------------------------------------------------- principal

def main():
    pular_img = '--sem-imagens' in sys.argv

    log("Reconstruindo a landing page como HTML estatico")
    log("")

    log("1. lendo o bundle")
    _, manifest, template = le_bundle()
    log(f"  {len(manifest)} recursos no manifest, template com {len(template)} chars")

    log("2. extraindo recursos embutidos")
    mapa_fontes = escreve_fontes(manifest)
    mapa_extra = escreve_logo(manifest)

    log("3. imagens")
    mapa_img = mapeia_imagens(manifest)
    dims = otimiza_imagens(mapa_img, pular=pular_img)

    log("4. montando o HTML")
    tpl = resolve_placeholders(template)
    tpl = resolve_condicionais(tpl)
    tpl = troca_imagens(tpl, mapa_img, mapa_extra, dims)
    doc = monta_html(tpl, mapa_fontes)

    destino = os.path.join(RAIZ, SAIDA)
    with open(destino, 'w', encoding='utf-8', newline='\n') as f:
        f.write(doc)
    log(f"  escrito: {SAIDA}")

    ok = confere(destino)
    log("")
    log("Build concluido." if ok else "Build concluido COM PENDENCIA — ver acima.")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
