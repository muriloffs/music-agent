# Music Agent — Design Spec (v1)

**Data:** 2026-05-19
**Status:** Brainstorming concluído, aguardando revisão final do usuário antes do plano de implementação.
**Próximo passo após aprovação:** invocar `superpowers:writing-plans` pra gerar plano detalhado.

---

## 1. Contexto

Projeto irmão do `cardiology-agent` (cardiologia diária) e `culture-agent` (cultura geral, filmes+música ampla). `music-agent` é dedicado: **um relatório semanal de música nova**, focado em descobertas alinhadas ao gosto do usuário e em pérolas de consenso crítico mesmo fora dele.

Restrições estruturais herdadas:
- Stack Python 3.11 (orquestrador) + Vue 3/Vite/Tailwind (frontend) + GitHub Actions (cron) + Vercel (deploy)
- Storage = JSON commitado em `data/` (versionado, gratuito, simples)
- LLMs: Haiku 4.5 (classify), Sonnet 4.6 (síntese), Gemini 2.5 (web search), Grok-4.3 (X/Twitter — opcional, com cache fallback)
- Frequência: **1 run/semana**

---

## 2. Tese do produto

> **Relatório semanal de música indie/art-rock anglo-americano (com dose leve de BR), em PT-BR, formato "Pulso + arquivo": destaques editoriais com prosa curta no topo + arquivo navegável de cards ricos abaixo. Cada card traz resumo da crítica, comparações sonoras, dicas de escuta e dados de contexto — pra você decidir o que ouvir antes de gastar 40 minutos com um disco.**

### 2.1 Decisões fixadas no brainstorming

| Decisão | Valor |
|---|---|
| Frequência | Semanal |
| Idioma do output | PT-BR brasileiro |
| Tom | Acessível, "vale a pena? para quem?" — não review acadêmico |
| Vibe | Pulso editorial (3-5 destaques com prosa) + arquivo de cards (~20-35 itens) |
| Geografia | INT primário (US/UK/Europa) + dose leve BR alinhada ao espírito |
| Tipos de release | Tudo: álbum + EP + single + mixtape + re-issue + live |
| Escopo v1 | Puro descoberta via fontes (sem Spotify API, sem lista de artistas seed) |
| Cron primário | Sábado 12:17 UTC (sáb 09:17 BRT) |
| Cron backup | Sábado 14:17 UTC |
| Modelos LLM | Haiku 4.5 (classify) + Sonnet 4.6 (síntese) + Gemini 2.5 (web) + Grok-4.3 (X, v2+) |

### 2.2 Perfil de gosto do usuário (síntese pra prompt)

Núcleo: **indie/art-rock anglo-americano de viés melancólico-literário**, com fatia de **eletrônica leftfield** e **folk americano/americana**. Detalhe e referências completas em `agent/prompts/perfil_gosto.txt` (a ser criado na implementação a partir do documento do usuário).

Atributos que o LLM deve usar pra inferir afinidade:
- Melancolia sofisticada, autenticidade emocional, densidade lírica
- Produção textural, atmosfera, reverberação emocional
- Capital simbólico (artistas "critic-driven"), prestígio crítico
- Identidade autoral forte, estranheza controlada, importância cultural
- Cenas: 4AD, Saddle Creek, Sub Pop, Domino, Bella Union, Jagjaguwar, Smalltown Supersound, Stones Throw
- Pontos de referência: Phoebe Bridgers, Big Thief, Sufjan, Bon Iver, Radiohead, Beach House, Floating Points, Tom Waits, Velvet Underground, Aldous Harding, Sampha, Fontaines DC

Equivalentes BR alinhados ao espírito (não exaustivo): Tim Bernardes, Sessa, Bala Desejo, Letrux, Tulipa Ruiz, Marcelo Camelo, Castello Branco.

---

## 3. Arquitetura de fontes — 3 camadas complementares

| Camada | Função | Tecnologia | Fontes v1 | Fontes v2+ |
|---|---|---|---|---|
| **A — RSS editorial** | Reviews longas, contexto crítico | `feedparser` + `httpx` | Stereogum, The Quietus, Aquarium Drunkard, Scream & Yell (BR) | + Bandcamp Daily, Loud and Quiet, NPR Music, Fact, Crack Magazine, Volume Morto, Pitchfork News |
| **B — Web search (consenso crítico)** | Captura Pitchfork/AOTY/RYM sem RSS | Gemini 2.5 com Google Search habilitado | 1 query semanal estruturada | Múltiplas queries (por gênero, por release type) |
| **C — Pulso de cena (X/Twitter)** | Hype emergente, anúncios artistas | Grok-4.3 API (X access) | Não na v1 | 1 query semanal com cache fallback |

**Princípio:** cada fonte é **1 arquivo Python isolado** em `agent/scripts/fetch_*.py` com a mesma assinatura (`fetch() -> list[dict]`). Falha em uma fonte **não derruba o pipeline** (lição 2). Adicionar fonte = adicionar 1 arquivo + 1 import.

### 3.1 Camada A — RSS editorial: fontes da v1

Todas validadas via `Invoke-WebRequest` em 2026-05-19. Resultados completos no Apêndice A.

| Fonte | URL | Items/feed | Encaixe |
|---|---|---|---|
| Stereogum | `https://www.stereogum.com/feed` (sem trailing `/`!) | 40 | Generalista forte indie/art-rock, mix de news+review |
| The Quietus | `https://thequietus.com/feed` | 32 | Crítica profunda, eletrônica leftfield, eccentric/cult |
| Aquarium Drunkard | `https://aquariumdrunkard.com/feed/` | 15 | Psych-folk/indie experimental — Animal Collective, Avey Tare, americana sofisticada |
| Scream & Yell (BR) | `https://screamyell.com.br/feed/` | 10 | Alternativo BR, cobertura de noise/post-punk/gothic, eventos culturais |

**Observação crítica:** Pitchfork RSS oficial (`/rss/reviews/best/albums/`) está **morto** — retorna 404. Cobertura de Pitchfork virá pela Camada B (Gemini Web Search) na v1. Pitchfork News RSS (`/rss/news/`) está vivo e entra na v2 como fonte de anúncios.

### 3.2 Camada B — Gemini Web Search: query estruturada

1 chamada Gemini 2.5 com Google Search tool habilitado, prompt-template:

```
Busque os melhores álbuns, EPs, singles, mixtapes e re-issues lançados ENTRE {data_inicio} e {data_fim} que receberam:
- Reviews de nota alta (>= 7.5/10 ou "Best New Music") em Pitchfork
- Score >= 80 no Album of the Year
- Score >= 4/5 no Rate Your Music ou Metacritic >= 80
- Cobertura crítica em pelo menos 2 publicações reconhecidas

Para cada item, retorne JSON estruturado com: artista, título, tipo, data, label, nota, fonte, url_review, resumo (1-2 frases). Inclua tanto itens dentro de indie/art-rock/eletrônica leftfield/folk quanto fora (jazz, clássica contemporânea, world, hip-hop) quando o consenso crítico for excepcional.
```

A camada B preenche dois papéis:
1. **Pitchfork-proxy** — substitui o RSS morto
2. **Cultural Consensus** — pérolas fora do nicho que valem destacar (jazz etíope, clássica avant, hip-hop conceitual)

### 3.3 Camada C — Grok no X (v2+)

Adiada pra v2. Query-template (já planejada):
```
Quais álbuns/singles indie/alternative/eletrônica leftfield foram lançados entre {data_inicio} e {data_fim} e estão sendo discutidos no X com volume notável? Foco em conversas de críticos, jornalistas musicais, labels e a própria conta dos artistas.
```

Grok-4.3 (não Grok-4 — descontinuado, lição 10). Cache fallback obrigatório (lição 9 — Grok 429 crônico no irmão).

### 3.4 Cache fallback — política geral (todas as fontes)

Aplica a **toda** chamada externa (RSS, Gemini, Grok), não só Grok. Padrão:

```python
def fetch_x():
    try:
        return live_fetch_with_retries()   # 3 tentativas, backoff 1s/2s (lição 2)
    except Exception:
        logger.warning(f"{source} falhou definitivamente; usando cache do último relatório")
        return load_from_last_committed_report(source)  # extrai itens dessa fonte do JSON anterior
```

Cards vindos de cache recebem flag `_cache_fallback: true` no JSON e no frontend aparecem com badge discreto "cache da semana anterior".

### 3.4 Fontes descartadas e por quê (Apêndice A)

| Fonte | Motivo |
|---|---|
| Pitchfork BNM/reviews RSS | 404 — RSS oficial morreu |
| Tiny Mix Tapes | SSL inválido, site abandonado |
| Fader | 404 — mudou estrutura |
| Vice/Noisey | Connection reset (Vice em colapso editorial) |
| Paste Music | Connection reset (paywall ou bloqueio) |
| Embrulhador BR | Conexão fechada pelo servidor (instável) |
| Monkeybuzz BR | Feed retorna vazio |
| TMDQA / Tracklist BR | Viés MPB tradicional/pop mainstream — longe do nicho |

---

## 4. Pipeline (1 run = 1 relatório semanal)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. FETCH PARALELO (asyncio)                                 │
│    - Camada A: 4 fontes RSS (3 INT + 1 BR)                  │
│    - Camada B: 1 Gemini Web Search call                     │
│    - Cada uma com 3 retries / backoff (lição 2)             │
│    - Cache fallback se falhar definitivamente               │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. NORMALIZE + DEDUP                                        │
│    - Schema unificado (item bruto)                          │
│    - Dedup por fuzzy match (artista_normalizado +           │
│      titulo_normalizado, similaridade >= 0.85)              │
│    - Mantém múltiplas fontes citando o mesmo item           │
│      (vira fontes_cobertura[] no card final)                │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. CLASSIFY (Haiku 4.5, paralelo)                           │
│    - Input: item bruto + perfil_gosto.txt                   │
│    - Output: {                                              │
│        bucket: "alinhado" | "media_afinidade"               │
│              | "consensus" | "br" | "noise",                │
│        afinidade_score: 0-10,                               │
│        razao_curta: "..."                                   │
│      }                                                       │
│    - Custo estimado: ~$0.05/run (~60 items × Haiku)         │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. ENRICH (Sonnet 4.6, 1 call por item dos buckets úteis)   │
│    - Só pros itens em bucket != "noise"                     │
│    - Para cada item, gera os 5 campos editoriais ricos:     │
│      resumo_critica, parecido_com, prestar_atencao,         │
│      dados_curiosos, vale_pra_voce                          │
│    - Custo: ~$0.10/run                                      │
│                                                              │
│    Alternativa otimizada (decidir no plano):                │
│    - Batch enrich em 1 call grande com todos os itens       │
│      úteis → mais barato, prompt mais complexo              │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. PULSO (Sonnet 4.6, 1 call)                               │
│    - Input: todos os cards enriquecidos                     │
│    - Output: 3-5 destaques editoriais com prosa curta       │
│      + tema da semana (opcional)                            │
│    - Custo: ~$0.10/run                                      │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. PERSIST                                                  │
│    - data/relatorio-YYYY-MM-DD.json                         │
│    - Git commit + push (workflow)                           │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. FRONTEND                                                 │
│    - api/report.js (Vercel func) lê JSON do GitHub raw      │
│    - App.vue renderiza Pulso + cards filtráveis por bucket  │
│    - Deploy automático Vercel                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Schema do JSON

```json
{
  "relatorio_data": "2026-05-23",
  "periodo_inicio": "2026-05-17",
  "periodo_fim": "2026-05-22",
  "versao_schema": "1.0",
  "nicho": "indie/art-rock anglo-americano + dose BR + consensus",

  "fontes_usadas": [
    {"id": "stereogum", "status": "ok", "items_brutos": 14},
    {"id": "quietus", "status": "ok", "items_brutos": 11},
    {"id": "aquarium_drunkard", "status": "ok", "items_brutos": 6},
    {"id": "scream_yell", "status": "ok", "items_brutos": 5},
    {"id": "gemini_web", "status": "ok", "items_brutos": 18}
  ],

  "stats": {
    "items_brutos_total": 54,
    "items_pos_dedup": 47,
    "items_classificados": 47,
    "items_no_relatorio": 28,
    "buckets": {
      "alinhado": 12,
      "media_afinidade": 8,
      "consensus": 5,
      "br": 3,
      "noise_descartado": 19
    },
    "custo_run_usd": 0.27,
    "duracao_segundos": 145
  },

  "pulso_da_semana": [
    {
      "id": "pulso_001",
      "is_destaque_principal": true,
      "titulo_tema": "Phoebe Bridgers volta solo após 4 anos",
      "prosa": "200-400 chars de prosa contextualizada em PT-BR. Cita 2-3 fontes, posiciona o lançamento na trajetória do artista, dá uma dica de escuta direta.",
      "cards_referenciados": ["card_007"]
    }
  ],

  "cards": [
    {
      "id": "card_007",
      "artista": "Phoebe Bridgers",
      "titulo": "Stranger in the Alps Revisited",
      "tipo": "album",
      "subtipo": null,
      "data_lancamento": "2026-05-22",
      "label": "Dead Oceans",
      "duracao_min": 47,
      "bucket": "alinhado",
      "afinidade_score": 9.5,
      "razao_curta_classify": "Núcleo absoluto do gosto — indie melancólico-literário, voz crítica consolidada",

      "resumo_critica": "Pitchfork (8.4) chama de 'o disco mais introspectivo de Bridgers desde Punisher'. Quietus elogia a produção minimalista de Tony Berg. Stereogum destaca a faixa 'Smoke Signals' como ponto alto da carreira.",
      "parecido_com": ["Punisher-era Phoebe meets Carrie & Lowell de Sufjan", "Atmosfera de Big Thief 'Two Hands' filtrada por dream pop"],
      "prestar_atencao": "Faixas 2 ('Smoke Signals') e 7 ('California Letters') são o coração do disco. Ouvir com headphones — mix tem detalhes de campo importantes. Primeiro álbum solo após o intervalo do supergrupo boygenius.",
      "dados_curiosos": "Produzido por Tony Berg (também responsável pelo Stranger in the Alps original de 2017). Convidados: Conor Oberst (faixa 4), Julien Baker (backing vocals em 'California Letters'). Gravado em Los Angeles entre setembro 2025 e março 2026.",
      "vale_pra_voce": "Encaixe direto no centro do seu mapa de gosto — indie melancólico-literário, autoria forte, produção textural. Se você gosta de Punisher e do disco do boygenius, este é prioritário.",

      "fontes_cobertura": [
        {"id": "stereogum", "url": "https://www.stereogum.com/...", "tipo": "review", "nota": null},
        {"id": "quietus", "url": "https://thequietus.com/...", "tipo": "review", "nota": null},
        {"id": "gemini_web", "url": "https://pitchfork.com/reviews/albums/phoebe-bridgers-stranger-revisited/", "tipo": "review", "nota": 8.4}
      ],

      "links": {
        "spotify": "https://open.spotify.com/album/...",
        "bandcamp": null,
        "apple_music": null,
        "youtube": null
      }
    }
  ]
}
```

### 5.1 Notas sobre o schema

- `bucket` controla onde o card aparece no frontend (4 abas/filtros)
- `links` pode ter campos `null` — frontend só renderiza ícones dos serviços com link
- `fontes_cobertura[]` permite mostrar "3 fontes cobriram" + clicar pra ler
- `versao_schema` deixa explícito o contrato — quebrar gera erro de parse no frontend
- `stats` é importante pra observabilidade (custo, duração, taxa de dedup)
- `afinidade_score` é 0-10 onde 10 = encaixe máximo no gosto (escala explícita no prompt do classify)
- Flag `_cache_fallback: true` no card quando vier de cache da semana anterior (renderiza badge no frontend)

### 5.2 Origem dos links (Spotify/Bandcamp/Apple/YouTube)

- **Fonte primária:** o próprio fetcher RSS extrai URLs quando o post original menciona. Stereogum/Pitchfork frequentemente embedam Spotify; Bandcamp Daily sempre tem link Bandcamp.
- **Fonte secundária:** o prompt de enrich (Sonnet 4.6) pode preencher `spotify`/`apple_music` quando consegue inferir o URI canonicamente (padrão `open.spotify.com/album/{id}`) — mas só quando há alta confiança.
- **Política de fallback:** se nenhuma fonte expõe link, o campo fica `null` e o frontend não renderiza o ícone correspondente. **Não fazemos** chamadas extras a APIs (Spotify, Bandcamp) só pra preencher links na v1 — fica pra v4.

---

## 6. Prompts — princípios e estrutura

3 prompts principais, todos em `agent/prompts/`:

### 6.1 `perfil_gosto.txt`
Documento permanente que descreve o gosto do usuário (gerado a partir do doc que ele colou em 2026-05-19). Estruturado em:
- Núcleo gravitacional (artistas-âncora)
- 8 ecossistemas com exemplos
- O que define o gosto (princípios abstratos: melancolia sofisticada, autenticidade etc)
- Equivalentes BR alinhados
- O que NÃO encaixa (EDM mainstream, hits massivos, pop puro etc)

Usado como `<perfil_gosto>...</perfil_gosto>` em todos os prompts subsequentes.

### 6.2 `classify_prompt.txt`
Roda por item, Haiku 4.5. Decide bucket + afinidade_score + razao_curta.

Princípios:
- Filtrar **por qualidade**, não por cota (lição 5 herdada)
- Sem regra numérica forçada ("X% dos cards devem ser bucket Y")
- Categorias claras, sem zona cinzenta: descreve no prompt o que define cada bucket
- Output JSON estruturado validado por `agent/parser.py`

### 6.3 `enrich_prompt.txt`
Roda por item (ou batch), Sonnet 4.6. Preenche os 5 campos editoriais ricos do card.

Princípios:
- Citar fontes literalmente ("Pitchfork chama de X")
- Comparações sonoras concretas, não genéricas ("não é só 'indie folk', é 'Sufjan da fase Illinois meets Big Thief Capacity')
- Dicas de escuta acionáveis ("faixa 3 é o pivô", "ouvir com headphones")
- Dados curiosos = produção/contexto histórico, não trivia barata
- "vale_pra_voce" só preenchido se bucket = "alinhado" ou "media_afinidade"

### 6.4 `pulso_prompt.txt`
Roda 1x por relatório, Sonnet 4.6. Gera 3-5 destaques editoriais com prosa.

Princípios:
- Tom: amigo crítico, não jornalista neutro nem fanboy
- Pode ter tema da semana (ex: "essa semana foi de retornos") se houver pattern
- Cada destaque referencia 1+ cards via `cards_referenciados[]`
- Prosa curta (200-400 chars), nunca review acadêmico

---

## 7. Frontend

### 7.1 Estrutura de páginas
- 1 página: `App.vue`
- Header com data do relatório, navegação entre relatórios passados
- Topo: **Pulso da Semana** (3-5 cards editoriais com prosa)
- Abaixo: **Arquivo de Cards** com 4 filtros/tabs:
  - 🎯 Alinhados ao gosto (bucket = "alinhado")
  - 🔍 Vale a pena explorar (bucket = "media_afinidade")
  - 🏆 Aclamados da semana (bucket = "consensus")
  - 🇧🇷 BR da semana (bucket = "br")
- Cada card: header (artista, título, tipo, label) + corpo com os 5 campos editoriais + footer com fontes/links

### 7.2 Componentes Vue
- `PulsoCard.vue` — destaque editorial com prosa
- `ReleaseCard.vue` — card de release expandível, mostra os 5 campos
- `BucketTabs.vue` — filtros por bucket
- `FontesFooter.vue` — lista de fontes citadas com links
- `LinksRow.vue` — ícones Spotify/Bandcamp/Apple/YouTube

### 7.3 Utilitários a copiar verbatim do cardiology
- `utils/openLink.js` — fix iOS Safari (lição 4)
- Estrutura geral de fetch do JSON via API Vercel
- Esqueleto Tailwind + Vite config

---

## 8. CI / Cron (GitHub Actions)

`.github/workflows/weekly-report.yml`:

```yaml
name: Weekly Music Report
on:
  schedule:
    - cron: '17 12 * * 6'   # sábado 12:17 UTC primário
    - cron: '17 14 * * 6'   # sábado 14:17 UTC backup (lição 3)
  workflow_dispatch:        # disparo manual sempre permitido
```

Step de idempotência (lição 3):
```yaml
- name: Check if this week's report already exists
  id: check_report
  run: |
    EXPECTED_DATE=$(TZ=America/Sao_Paulo date +%Y-%m-%d)
    if [ -f "data/relatorio-${EXPECTED_DATE}.json" ]; then
      echo "skip=true" >> "$GITHUB_OUTPUT"
    fi
```

Cada step subsequente:
```yaml
if: github.event_name == 'workflow_dispatch' || steps.check_report.outputs.skip != 'true'
```

---

## 9. Secrets

GitHub Actions (Settings → Secrets and variables → Actions):
- `ANTHROPIC_API_KEY` (Haiku + Sonnet)
- `GOOGLE_API_KEY` (Gemini 2.5 Web Search)
- *(v2)* `XAI_API_KEY` (Grok-4.3)

Vercel (mesmas chaves para Edge Functions, se necessário no frontend — provavelmente não, frontend só lê JSON).

---

## 10. Custos

| Item | Custo unitário | Volume/mês | Total/mês |
|---|---|---|---|
| Classify Haiku 4.5 | $0.05/run | 4 runs | $0.20 |
| Enrich + Pulso Sonnet 4.6 | $0.20/run | 4 runs | $0.80 |
| Gemini Web Search | $0.01/run | 4 runs | $0.04 |
| GitHub Actions (repo público) | $0 | — | $0 |
| Vercel (free tier) | $0 | — | $0 |
| **Total** | | | **~$1.05/mês** |

5-10x mais barato que o cardiology (~$10/mês diário). Margem confortável.

---

## 11. Roadmap pós-v1

### v2 — semanas 2-6 após v1 estável
- Adicionar 6 fontes RSS extras (1 por semana, isoladas como `fetch_*.py`): Bandcamp Daily, Loud and Quiet, NPR Music, Fact, Crack Magazine, Volume Morto, Pitchfork News
- Ativar Camada C (Grok-4.3 em X) com cache fallback
- Filtros adicionais no frontend (por tipo: álbum/EP/single/reissue/live)

### v3 — após v2 maduro
- **Camada 1 "Never Miss"** via Spotify Web API: lista curada de 20-30 artistas-âncora, consulta semanal de `/artists/{id}/albums`, garante captura mesmo se nenhuma fonte editorial cobrir
- Frontend: badge "monitorado" em cards da Camada 1

### v4 — exploratório
- HTML scrape de Pitchfork reviews (se Gemini Web Search deixar a desejar)
- Player Spotify embed por card (sem login, só preview 30s)
- Newsletter export (markdown + envio email via Resend ou similar)

### v5 — features de longo prazo (não compromissadas)
- Recomendador feature-based (atributos MusicBrainz + similaridade)
- Embeddings de descrições/letras pra "mais como este"
- Histórico anual ("o que apareceu em N+ semanas em 2026?")

---

## 12. Critérios de "v1 pronta"

Considera-se a v1 pronta quando:
1. ✅ `git push` ao `main` dispara o workflow do GH Actions
2. ✅ Workflow roda no cron sábado 12:17 UTC sem intervenção manual
3. ✅ 4 fontes RSS + Gemini Web Search retornam dados sem falhar (cache fallback testado)
4. ✅ JSON do relatório é commitado em `data/` automaticamente
5. ✅ Frontend Vercel deploya automático e mostra Pulso + cards filtrados por bucket
6. ✅ Links iOS Safari funcionam (lição 4 aplicada com `openLink.js`)
7. ✅ Custo do primeiro run real está dentro de ±50% da estimativa ($1.05/mês)
8. ✅ Pelo menos 1 ciclo end-to-end completo: cron dispara → JSON commitado → frontend renderiza → você lê

---

## 13. Decisões deliberadamente postergadas

| Decisão | Por que postergada | Quando revisitar |
|---|---|---|
| Lista de artistas "Never Miss" + Spotify API | Adiciona complexidade arquitetural significativa antes da v1 estabilizar | v3 (após v2 maduro) |
| HTML scrape de Pitchfork | Gemini Web Search deve cobrir, e scrape é frágil | v4, se Gemini não der conta |
| Player Spotify embed | Não-essencial pra MVP "vale a pena ouvir?" | v4 |
| Grok no X | Pulso de cena é "nice to have", LLM Sonnet já infere razoavelmente | v2 |
| Recomendador feature-based / embeddings | Prompt-based via Sonnet 4.6 já é surpreendentemente bom; só investir mais se ficar evidente que está insuficiente | v5, baseado em uso real |
| Nome final do projeto (vs `music-agent` default) | Repo já existe como `music-agent`; branding do produto pode mudar depois | Antes do primeiro deploy Vercel — escolher entre `pulso musical`, `weekly tape`, `semanário`, ou manter `music-agent` |

---

## 14. Riscos conhecidos e mitigações

| Risco | Probabilidade | Mitigação |
|---|---|---|
| Stereogum/Quietus mudam URL do feed (Pitchfork-like) | Média | Validação periódica + cache fallback obrigatório |
| Gemini Web Search retorna dados imprecisos | Média | Cross-check com 2+ fontes RSS antes de aceitar como "consensus" |
| LLM Sonnet hallucina campos editoriais (review_inexistente) | Média-alta | Prompt explícito "cite só o que está no input"; validação no parser pra rejeitar citações sem fonte |
| GitHub Actions atrasa/pula o cron | Média (lição 3) | Backup às 14:17 UTC + dispatch manual sempre disponível |
| Volume de release Friday flutua muito | Alta | Schema aceita 5 a 100 cards/semana; frontend é elástico |
| Fonte BR (Scream & Yell) pode ter cobertura irregular | Alta | Não é fonte crítica — relatório roda sem BR se falhar |
| Custo de LLM aumenta com escala (Gemini Search) | Baixa | $1/mês é margem grande; quando v2 adicionar fontes, reavaliar |

---

## 15. Definition of done por arquivo (alto nível)

Pra o `writing-plans` poder gerar tarefas atômicas:

```
music-agent/
├── README.md                           — visão do produto + screenshots + custo
├── .gitignore                          — herdar do cardiology
├── docs/superpowers/specs/             — este spec + futuros
├── agent/
│   ├── agent.py                        — biblioteca: classes/funções das fases (pure logic, testável)
│   ├── parser.py                       — valida JSON do LLM (schema 1.0)
│   ├── requirements.txt                — anthropic, google-generativeai, feedparser, httpx, etc
│   ├── prompts/
│   │   ├── perfil_gosto.txt            — gerado a partir do doc do usuário
│   │   ├── classify_prompt.txt
│   │   ├── enrich_prompt.txt
│   │   └── pulso_prompt.txt
│   ├── scripts/
│   │   ├── fetch_stereogum.py
│   │   ├── fetch_quietus.py
│   │   ├── fetch_aquarium_drunkard.py
│   │   ├── fetch_scream_yell.py
│   │   ├── fetch_gemini_web.py
│   │   └── generate_report.py          — entry point chamado pelo CI: importa agent.py, executa pipeline end-to-end, salva JSON
│   └── tests/
│       ├── test_parser.py
│       ├── test_dedup.py
│       └── test_fetch_*.py             — 1 por fonte, com fixtures HTML/RSS
├── api/
│   └── report.js                       — Vercel function lê JSON do GitHub raw
├── data/
│   └── .gitkeep
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── src/
│       ├── App.vue
│       ├── main.js
│       ├── components/
│       │   ├── PulsoCard.vue
│       │   ├── ReleaseCard.vue
│       │   ├── BucketTabs.vue
│       │   ├── FontesFooter.vue
│       │   └── LinksRow.vue
│       └── utils/
│           ├── openLink.js             — COPIAR verbatim do cardiology
│           └── formatters.js
├── vercel.json
└── .github/
    └── workflows/
        └── weekly-report.yml
```

---

## Apêndice A — Validação curl das fontes (2026-05-19)

### A.1 Fontes confirmadas funcionando

| Fonte | URL | HTTP | Items | Encaixe gosto | Aceita v1? |
|---|---|---|---|---|---|
| Stereogum | https://www.stereogum.com/feed | 200 | 40 | Alto | ✅ Sim |
| The Quietus | https://thequietus.com/feed | 200 | 32 | Alto | ✅ Sim |
| Aquarium Drunkard | https://aquariumdrunkard.com/feed/ | 200 | 15 | Alto | ✅ Sim |
| Scream & Yell (BR) | https://screamyell.com.br/feed/ | 200 | 10 | Médio-alto | ✅ Sim |
| Pitchfork News | https://pitchfork.com/rss/news/ | 200 | 29 | Médio | v2 |
| NPR Music | https://feeds.npr.org/1039/rss.xml | 200 | 10 | Médio-alto | v2 |
| Loud and Quiet | https://www.loudandquiet.com/feed/ | 200 | 10 | Alto | v2 |
| Brooklyn Vegan | https://www.brooklynvegan.com/feed/ | 200 | 15 | Médio (volume alto) | v2 |
| Consequence | https://consequence.net/category/music/feed/ | 200 | 15 | Baixo-médio | Talvez v3 |
| Crack Magazine | https://crackmagazine.net/feed/ | 200 | 99 | Médio-alto (electronic) | v2 |
| Fact Magazine | https://www.factmag.com/feed/ | 200 | 10 | Médio-alto | v2 |
| Bandcamp Daily | https://daily.bandcamp.com/feed | 200 | (RSS válido) | Alto | v2 |
| Volume Morto (BR) | https://volumemorto.substack.com/feed | 200 | 1 | Alto (vibe) — baixo volume | v2 |

### A.2 Fontes descartadas

| Fonte | Razão |
|---|---|
| Pitchfork BNM RSS (`/rss/reviews/best/albums/`) | HTTP 404 — desligado |
| Pitchfork Reviews RSS (`/rss/reviews/albums/`) | HTTP 404 — desligado |
| Tiny Mix Tapes | SSL inválido, site abandonado |
| Fader | HTTP 404 |
| Vice/Noisey | Connection reset (colapso editorial) |
| Paste Music | Connection reset |
| Embrulhador (BR) | Connection reset (servidor instável) |
| Monkeybuzz (BR) | Feed retorna vazio |
| TMDQA (BR) | Viés MPB tradicional, longe do nicho |
| Tracklist (BR) | Viés pop mainstream (manchete Harry Styles) |

---

**Fim do spec.** Aguardando revisão do usuário antes de invocar `writing-plans`.
