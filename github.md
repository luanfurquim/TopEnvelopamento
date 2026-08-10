repo: luanfurquim/TopEnvelopamento
branch: main
deploy: HostGator cPanel → Git Version Control (.cpanel.yml publica em public_html/)

## Last sync
date: 2026-08-10
commit: correção de SEO + conversão de WhatsApp

### Atualizado em 10/08/2026
- **Tags de SEO movidas para dentro do `<helmet>`** — ver "Como reconstruir" abaixo
- `og:image` e `twitter:image` agora com URL absoluta (o preview falhava com caminho relativo)
- `meta description` reduzida de 200 para 149 caracteres (o Google cortava em ~155)
- Email corrigido: `topevenlopamento@` → `topenvelopamento@` (rodapé e JSON-LD)
- Script de conversão de clique no WhatsApp para o Google Ads (`AW-16763500925`)
- `.cpanel.yml` passou a publicar `google*.html` — o arquivo de verificação do
  Search Console estava no repo mas respondia 404 no ar

## Onde as tags de SEO precisam ficar

O `index.html` é um bundle: o documento real vai como string dentro de um
`<script>` no fim do arquivo e o runtime **substitui o documento inteiro** ao
carregar. Só o conteúdo do `<helmet>` sobrevive.

Tudo que for colocado no `<head>` externo do `index.html` é descartado antes
de o Googlebot ler a página. **Toda tag de SEO vai dentro do `<helmet>`** do
`Top Envelopamento PPF.dc.html`.

*(A nota anterior dizia que "o bundler só preserva o `<title>`" e por isso
mandava reinjetar tudo no `<head>` do bundle a cada build. Era esse o erro:
o bundler preserva o `<helmet>` inteiro.)*

## Como reconstruir o index.html
1. Editar `Top Envelopamento PPF.dc.html` — inclusive as tags de SEO, que
   agora moram no `<helmet>` dele
2. Gerar `standalone-src.dc.html` (cópia sem a referência a image-slot.js)
3. Compilar em `index.html` (bundle autocontido)
4. **Não é mais necessário reinjetar nada no `<head>`.** Conferir só se o
   `<helmet>` veio completo.

## Verificar depois de cada deploy
- [Teste de Resultados Aprimorados](https://search.google.com/test/rich-results)
  deve encontrar `AutoBodyShop` e `FAQPage`
- [Sharing Debugger](https://developers.facebook.com/tools/debug/) para
  atualizar o cache do preview do WhatsApp
- Clicar num botão de WhatsApp com o Tag Assistant aberto e conferir se sai
  o evento `conversion`

## Estrutura de pastas

| Pasta | Papel | Vai pro servidor? |
| --- | --- | --- |
| `img/` | fotos-fonte, usadas pelo `.dc.html` ao editar/reconstruir | não |
| `img-bundle/` | as mesmas fotos, referenciadas pelo `index.html` compilado | sim |
| `assets/` | og-image.jpg, favicon.svg, favicon.png | sim |

As duas pastas de imagem têm arquivos byte a byte idênticos (17 em cada), mas
**as duas são necessárias**: uma é fonte de edição, a outra é saída de build.
Apagar `img/` inviabiliza reconstruir o site a partir do `.dc.html`.

## Screen map
| Tela | Arquivos de origem |
| --- | --- |
| Landing page PPF (index.html) | Top Envelopamento PPF.dc.html → standalone-src.dc.html → index.html |
| Fotos | img/ (hero, porsche, 01–11, wpf-01–04) |
| Compartilhamento | assets/og-image.jpg, assets/favicon.svg |
