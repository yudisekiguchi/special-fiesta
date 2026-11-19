# Busca Segura de Torrents

App web local que busca **música, vídeo e imagens** em vários sites de torrent
ao mesmo tempo e dá uma **nota de confiança** para cada resultado:

- 🟢 **Confiável**: sinais bons (uploader com selo, muitos seeders, arquivos coerentes)
- 🟡 **Atenção**: sinais mistos, confira antes de baixar
- 🔴 **Evitar**: executáveis, tamanho incoerente, termos de golpe etc.

O app **não baixa nada**. Ele mostra o link magnet ou o `.torrent` para você
abrir no seu cliente (qBittorrent, Transmission...).

> A nota é uma estimativa, não uma garantia. Passe o antivírus no que baixar
> (no Ubuntu: `sudo apt install clamav && clamscan -r ~/Downloads/pasta`).

## Como rodar (Ubuntu)

```bash
sudo apt install python3-venv   # só na primeira vez
git clone <este repositório> && cd special-fiesta
./run.sh
```

Depois abra http://127.0.0.1:8000. O servidor só aceita conexões do próprio notebook.

## Fontes

| Fonte | Como acessa | Observação |
|---|---|---|
| The Pirate Bay | API JSON (`apibay.org`) | Verifica a lista de arquivos dos 8 primeiros |
| 1337x | HTML do site | Usa Cloudflare; às vezes bloqueia. Domínios em `BASE_URLS` |
| Internet Archive | API oficial | Acervo legal (domínio público / Creative Commons) |

Software, jogos e conteúdo adulto são filtrados.

## Como a nota é calculada

Começa em 50 e soma/subtrai (ver `app/scoring.py`):

| Sinal | Pontos |
|---|---|
| Executável no nome ou nos arquivos (`.exe`, `.scr`, `.bat`, `.lnk`...) | −60/−70 e **sempre vermelho** |
| Termos de golpe no nome (`codec`, `password`, `crack`, `setup`...) | −25 |
| Arquivos compactados (`.zip`, `.rar`...) | −20 |
| Nenhum arquivo do tipo esperado | −30 |
| Tamanho pequeno demais (ex.: vídeo < 50 MB) | −30 |
| 0 seeders / muitos leechers e quase nenhum seeder | −20 / −10 |
| Arquivos com extensão esperada | +10 |
| Seeders: 5+, 50+, 500+ | +5 / +12 / +20 |
| Uploader confiável / VIP | +15 / +20 |
| Mesmo hash em outros sites | +10 por site (máx. +20) |
| Fonte oficial (Internet Archive) | +35 |

≥ 70 verde · 40–69 amarelo · < 40 vermelho.

## Adicionar um site

1. Crie `app/adapters/meusite.py` com uma classe que herda de `SiteAdapter`
   e implementa `search(query, media)` retornando `TorrentResult`s.
2. Registre em `app/adapters/__init__.py`.
3. Adicione um teste em `tests/` com um HTML/JSON de exemplo.

## Testes

```bash
.venv/bin/pip install pytest && .venv/bin/python -m pytest
```
