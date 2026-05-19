# Music Agent — Referência Arquitetural

> Stack proposta, espelhando cardiology-agent com adaptações para música/semanal.
> Ajustar conforme decidir nicho e fontes.

## Pipeline (1 run = 1 relatório semanal)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. FETCH PARALELO das fontes (Python, asyncio ou ThreadPool)│
│    - Cada fonte: 1 função independente em scripts/fetchers/ │
│    - Falha em uma fonte NÃO derruba o pipeline              │
│    - Cache fallback se fonte falhar (carrega último válido) │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. NORMALIZAÇÃO + DEDUP                                     │
│    - Schema único: {titulo, artista, ano, fonte, url, ...}  │
│    - Dedup por (artista + título) — fuzzy match             │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. CLASSIFICAÇÃO (LLM 1: barato, paralelizável)             │
│    - Para cada item: classe A/B/C + categoria + score       │
│    - Modelo: Haiku 4.5 / Gemini Flash / GPT-4o-mini         │
│    - Streaming response                                     │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. SÍNTESE / CURADORIA (LLM 2: capaz, 1 call)               │
│    - Gera "Pulso da Semana" — top destaques com contexto    │
│    - Modelo: Sonnet 4.6 / Gemini 2.5 Pro / GPT-4o           │
│    - Input: items classificados + histórico semanas         │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. PERSIST                                                  │
│    - data/relatorio-YYYY-MM-DD.json (nome = data do run)    │
│    - Git commit + push (automatizado pelo workflow)         │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. FRONTEND (Vue 3 + Vite + Tailwind)                       │
│    - api/report.js (Vercel function) lê JSON do GitHub raw  │
│    - App.vue renderiza cards por categoria                  │
│    - Deploy automático Vercel a cada push                   │
└─────────────────────────────────────────────────────────────┘
```

## Stack proposta

| Camada | Tecnologia | Por quê |
|---|---|---|
| Orquestrador | Python 3.11 | Mesma do cardiology, agent.py é o entry point |
| LLM classify | Haiku 4.5 OU Gemini Flash | Barato + paralelo |
| LLM síntese | Sonnet 4.6 OU Gemini 2.5 Pro | Equilíbrio qualidade/preço |
| Frontend | Vue 3 + Vite + Tailwind | Mesma do cardiology, build rápido |
| CI/CD | GitHub Actions | Cron + commit automático |
| Deploy | Vercel | Free tier OK para tráfego pessoal |
| Storage | JSON commitado em `data/` | Simples, versionado, grátis |

## Custos estimados (mensais)

| Item | Custo |
|---|---|
| LLMs (4 runs/mês × ~$0.30) | ~$1.20 |
| GitHub Actions (repo público) | $0 |
| Vercel (free tier) | $0 |
| APIs externas (depende do nicho) | $0-3 |
| **Total estimado** | **~$1-5/mês** |

Cardiology custa ~$10/mês porque roda diário e tem mais fontes. Music semanal
é ~5-10x mais barato.

## Estrutura de pastas (espelhando cardiology)

```
music-agent/
├── .github/
│   └── workflows/
│       └── weekly-report.yml          # cron semanal
├── agent/
│   ├── agent.py                       # entry point — chama todas as fases
│   ├── parser.py                      # validação schema do output do LLM
│   ├── prompt.txt                     # prompt principal da classificação
│   ├── prompts/
│   │   ├── pulso_prompt.txt           # prompt da síntese semanal
│   │   └── ...
│   ├── scripts/
│   │   ├── fetch_pitchfork.py         # 1 arquivo por fonte
│   │   ├── fetch_stereogum.py
│   │   ├── fetch_<nicho>.py
│   │   └── generate_report.py         # orchestrator chamado pelo CI
│   ├── requirements.txt
│   └── tests/
├── api/
│   └── report.js                      # Vercel function
├── data/
│   └── relatorio-YYYY-MM-DD.json      # 1 por semana
├── frontend/
│   ├── src/
│   │   ├── App.vue
│   │   ├── components/
│   │   │   ├── ReleaseCard.vue
│   │   │   ├── PulsoCard.vue
│   │   │   └── ...
│   │   └── utils/
│   │       ├── openLink.js            # COPIAR do cardiology (iOS fix)
│   │       └── ...
│   ├── package.json
│   └── vite.config.js
├── vercel.json
├── README.md
└── docs/
    └── ...
```

## Schema do relatório (sugestão inicial — adaptar)

```json
{
  "relatorio_data": "2026-05-23",
  "periodo_inicio": "2026-05-17",
  "periodo_fim": "2026-05-23",
  "nicho": "<DEFINIR>",

  "lancamentos": [
    {
      "id": "rel_001",
      "titulo": "Album/single name",
      "artista": "Artist name",
      "tipo": "album|ep|single|mixtape",
      "data_lancamento": "2026-05-20",
      "label": "Label name",
      "duracao_min": 42,
      "classe": "A|B|C",
      "score": 8.5,
      "categoria_fonte": "critico|blog|spotify|playlist",

      "resumo": "1-2 frases em PT-BR sobre o que é",
      "vale_a_pena": "Para quem este lançamento faz sentido",
      "referencias_sonoras": ["Artista X (2020)", "Banda Y meets Z"],

      "links": {
        "spotify": "https://open.spotify.com/album/...",
        "bandcamp": "https://...",
        "review_url": "https://pitchfork.com/...",
        "youtube": "https://..."
      }
    }
  ],

  "pulso_da_semana": [
    {
      "id": "pulso_001",
      "is_destaque_da_semana": true,
      "titulo": "Frase concisa do tema",
      "razao_destaque": "Por que essa semana",
      "o_que_diz_a_critica": "2-3 frases sobre recepção crítica",
      "para_quem": "Recomendação direcionada",
      "fontes_cobertura": [{"tipo": "critico", "id": "rev_005"}]
    }
  ],

  "criticas": [],
  "discussoes": [],
  "playlist_da_semana": null
}
```

## Cron sugerido

Para entrega no fim de semana (relatório pronto sábado de manhã):

```yaml
on:
  schedule:
    # Primário: sexta 22:17 UTC (sexta 19:17 BRT)
    # Captura semana completa de releases (terça típico de lançamento)
    - cron: '17 22 * * 5'
    # Backup: sábado 00:17 UTC (sexta 21:17 BRT)
    - cron: '17 0 * * 6'
  workflow_dispatch:
```

Coordena com cardiology-agent (que ficou em 04:17 UTC) — sem conflito de
fila no scheduler.

**Decisão pendente:** confirmar dia/horário com o usuário no chat dedicado.
Outras opções: terça noite (resumo da semana anterior), domingo cedo (preview
da semana), etc.

## Decisões a tomar antes de codificar (lista para o chat dedicado)

- [ ] Nicho específico (define quais fontes integrar)
- [ ] Lista de 4-6 fontes para começar (validar cada uma com `curl` antes)
- [ ] Modelo principal (Claude/Gemini/OpenAI — todos servem)
- [ ] Dia e horário do cron semanal
- [ ] Tem cache fallback para fontes que podem falhar?
- [ ] Frontend tem filtros (gênero, formato, label)?
- [ ] Inclui campo de "playlist da semana" (Spotify embed)?
