repo: luanfurquim/IArobot
branch: main
deploy: HostGator cPanel → Git Version Control (.cpanel.yml publica em public_html/)

## Last sync
date: 2026-07-31T00:00:00Z
commit: (nenhum — repositório vazio; primeiro push pendente do usuário)

### Updated in this project
- index.html: arquivo único autocontido (3,4 MB) com as 17 fotos, fontes e runtime embutidos — sem CDN
- Metadados de SEO e compartilhamento (description, Open Graph, Twitter card, lang=pt-BR) + assets/og-image.jpg e favicon
- .cpanel.yml, .gitignore, .htaccess (gzip + cache) e robots.txt para deploy via cPanel
- Links de WhatsApp normalizados para 5517991883704

## Como reconstruir o index.html
1. Editar `Top Envelopamento PPF.dc.html`
2. Gerar `standalone-src.dc.html` (cópia sem a referência a image-slot.js)
3. Compilar em `index.html` (bundle autocontido)
4. Reinjetar no `<head>` real do bundle: viewport, description, theme-color, robots, Open Graph, Twitter card, favicon e `lang="pt-BR"` (o bundler só preserva o `<title>`)

## Screen map
| Tela | Arquivos de origem |
| --- | --- |
| Landing page PPF (index.html) | Top Envelopamento PPF.dc.html → standalone-src.dc.html → index.html |
| Fotos | img/ (hero, porsche, 01–11, wpf-01–04) |
| Compartilhamento | assets/og-image.jpg, assets/favicon.svg |
