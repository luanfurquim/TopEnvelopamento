repo: luanfurquim/TopEnvelopamento
branch: main
deploy: HostGator cPanel → Git Version Control (.cpanel.yml publica em public_html/)

## Last sync
date: 2026-08-14
commit: landing page vira HTML estático + carrossel sobe para a 3ª seção

### Atualizado em 14/08/2026 — a mudança que importa

**O `index.html` deixou de ser um bundle e passou a ser HTML de verdade.**

O que estava no ar era o arquivo de preview do construtor: todo o conteúdo
viajava como string JSON dentro de `<script type="__bundler/template">` e o
JavaScript montava a página no navegador. Funcionava para humano e era
invisível para robô — sem executar JS, a página tinha 0 seção, 0 imagem e
0 botão de WhatsApp. O site não estava indexado no Google.

| | Antes | Depois |
|---|---|---|
| Seções em HTML real | 0 de 10 | 10 de 10 |
| Imagens em HTML real | 0 de 28 | 28 de 28 |
| Botões de WhatsApp em HTML real | 0 de 6 | 6 de 6 |
| Texto visível sem executar JS | 1.340 (era CSS) | 16.923 |
| `index.html` | 429 KB | 85 KB |
| Peso de imagem | 2,29 MB | 1,05 MB (WebP) |
| JS para a página existir | React + ReactDOM + runtime (212 KB) | nenhum |

Junto vieram: `lang="pt-BR"` estático, `width`/`height` em todas as imagens
(acaba o salto de layout), `fetchpriority="high"` no hero, `loading="lazy"`
no resto, WebP com fallback JPG via `<picture>`, e o menu hambúrguer escrito
no HTML em vez de injetado por um script que rodava a cada 100 ms.

**A ordem das seções mudou:** o carrossel de projetos saiu da 7ª posição
(dobra 10,3 de 14 no celular, visto por ~22% de quem entra) para a 3ª
(dobra 2,1). O bloco técnico do QuadFilm desceu para depois da prova visual.
A decisão está documentada no workspace de tráfego, em
`02-LANDING-PAGE/diagnostico-2026-08-14/05-carrossel-decisao.md`.

## Como reconstruir o index.html

```
Top Envelopamento PPF.dc.html   (edição no construtor)
    -> index.bundle.html        (saída compilada do construtor)
    -> python build.py          (novo passo — não pular)
    -> index.html               (estático, é o que vai pro ar)
```

1. Editar `Top Envelopamento PPF.dc.html` — as tags de SEO moram no
   `<helmet>` dele
2. Compilar no construtor e salvar a saída como **`index.bundle.html`**
   (não como `index.html`)
3. Rodar `python build.py`
4. Conferir que a conferência no fim saiu toda `[OK]`

**Se pular o passo 3, o bundle volta pro ar e a página fica invisível de
novo.** O `build.py` recusa rodar se não achar um bundle válido.

### Para mudar a ordem das seções

Editar `ORDEM_SECOES` no topo do `build.py` e rodar de novo. Cada número é a
posição da seção no template original.

### Requisito

`python build.py` precisa do [Pillow](https://pypi.org/project/Pillow/) para
otimizar imagem: `pip install Pillow`. Sem ele o build roda mesmo assim, só
copia as imagens sem reduzir e avisa.

Use `python build.py --sem-imagens` para pular a otimização quando estiver
mexendo só em texto ou ordem — é bem mais rápido.

## Verificar depois de cada deploy

- [Teste de Resultados Aprimorados](https://search.google.com/test/rich-results)
  deve encontrar `AutoBodyShop` e `FAQPage`
- Search Console → **Inspeção de URL** → **Testar URL ativo**: o HTML
  renderizado tem que trazer as 10 seções
- [Sharing Debugger](https://developers.facebook.com/tools/debug/) para
  atualizar o cache do preview do WhatsApp
- Clicar num botão de WhatsApp com o Tag Assistant aberto e conferir se sai
  o evento `conversion` (`AW-16763500925/Lr_VCIP2st8cEP3yurk-`)
- Conferir que nenhuma imagem responde 404: o `.htaccess` tem
  `ErrorDocument 404 /index.html`, então imagem faltando devolve a página
  inteira em vez de um erro visível

## Estrutura de pastas

| Pasta | Papel | Vai pro servidor? |
| --- | --- | --- |
| `img/` | fotos originais, fonte do build | não |
| `assets/img/` | saída do build: JPG redimensionado + WebP | **sim** |
| `assets/fonts/` | as 7 woff2, extraídas do bundle | **sim** |
| `assets/` | og-image.jpg, favicon.svg, favicon.png, logo-top.svg | **sim** |

`img-bundle/` **foi removida em 14/08/2026.** Era cópia byte a byte de `img/`
(17 arquivos, 2,4 MB) e só servia para o `build.py` descobrir qual UUID do
bundle correspondia a qual foto. Essa correspondência agora está gravada em
`build-imagens.json`.

Se um dia o construtor gerar UUIDs novos (troca de fotos), o `build.py` avisa
e o caminho é restaurar `img-bundle/` do histórico do git, rodar uma vez para
regravar o mapa, e apagar de novo.

## Screen map

| Tela | Arquivos de origem |
| --- | --- |
| Landing page PPF | Top Envelopamento PPF.dc.html → index.bundle.html → build.py → index.html |
| Fotos | img/ (hero, porsche, 01–11, wpf-01–04) → assets/img/ |
| Compartilhamento | assets/og-image.jpg, assets/favicon.svg |
