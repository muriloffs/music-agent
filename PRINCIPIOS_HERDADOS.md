# Princípios herdados do cardiology-agent

> Lições aprendidas a duro custo no projeto irmão. **Leia antes de codar.**
> Cada princípio aqui economiza de horas a dias de retrabalho.

## 1. Validar PREMISSA antes de codificar feature

**A maior lição.** Antes de escrever 200 linhas integrando uma API X, faça
**1 chamada `curl`** à API X com dados reais do seu domínio. Pergunte:
> "Vai retornar o que eu preciso, no volume que preciso, com o atraso aceitável?"

**Exemplo de armadilha (cardiology-agent):** integrei PMC figures (~200 linhas
Python + UI Vue) sem testar primeiro se papers do dia estão no PMC OA. NÃO
estão (latência de meses entre PubMed e PMC OA indexar). Resultado: feature
desligada após 2 dias.

**Para música:** antes de integrar `<fonte X>`, rode `curl <endpoint>` e
veja se o feed dela traz os tipos de coisa que você quer **na frequência
semanal**. Algumas fontes têm reviews diários (Pitchfork), outras semanais
(NPR Music), outras mensais (revistas).

## 2. Defesa em profundidade para chamadas externas

Toda chamada a API externa precisa:

```python
def call_external_api(payload, max_attempts=3):
    last_err = None
    data = None
    for attempt in range(1, max_attempts + 1):
        try:
            if attempt == max_attempts:
                # Última tentativa: POST (NCBI recomenda para listas grandes;
                # outros servidores podem rejeitar GET com query string longa)
                response = requests.post(URL, data=payload, timeout=30)
            else:
                response = requests.get(URL, params=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            break
        except Exception as e:
            last_err = e
            logger.info(f"attempt {attempt}/{max_attempts} failed: {e}")
            if attempt < max_attempts:
                time.sleep(attempt)  # backoff 1s, 2s
    if data is None:
        logger.warning(f"failed after {max_attempts} attempts: {last_err}")
        return {}  # ou raise, dependendo do downstream
    return parse(data)
```

**Princípios:**
- 3 tentativas com backoff progressivo (1s, 2s)
- Última tentativa usa POST (alguns servidores cortam URLs longas no GET)
- Logs `INFO` durante retries (não polui), `WARNING` só na falha definitiva
- Retorno explícito (`{}`/`[]`) faz downstream pular **explicitamente** (não silenciosamente)
- Para dado crítico, considere `raise` em vez de retorno vazio — orchestrator decide

## 3. Cron do GitHub Actions tem AZAR sistêmico

**Sintoma:** crons agendados em `0 X * * *` atrasam 1-3h ou pulam completamente.

**Causa documentada pelo GH:** "Schedule event can be delayed during periods of
high loads. **High load times include the start of every hour.**"

**Solução padrão (aplicar sempre):**

```yaml
on:
  schedule:
    # Primário: minuto 17 ou outro off-peak (não 0)
    - cron: '17 22 * * 6'  # Sábado 22:17 UTC — janela quieta
    # Backup: mesmo dia, +2h. Se primário pular, backup pega
    - cron: '17 0 * * 0'   # Domingo 00:17 UTC
  workflow_dispatch:        # sempre permitir disparo manual via gh
```

**Step de idempotência** (impede backup duplicar custo se primário rodou):

```yaml
- name: Check if today's report already exists
  id: check_report
  run: |
    EXPECTED_DATE=$(TZ=America/Sao_Paulo date +%Y-%m-%d)
    EXPECTED_FILE="data/relatorio-${EXPECTED_DATE}.json"
    if [ -f "$EXPECTED_FILE" ]; then
      echo "skip=true" >> "$GITHUB_OUTPUT"
    else
      echo "skip=false" >> "$GITHUB_OUTPUT"
    fi

# Cada step subsequente:
# if: github.event_name == 'workflow_dispatch' || steps.check_report.outputs.skip != 'true'
```

**Janelas documentadamente quietas:**
- 4-6 UTC (madrugada Europa, fim de tarde Ásia)
- 22-00 UTC (Europa dormiu, Ásia ainda não acordou)

**Evitar:**
- 7-9 UTC (início expediente Europa — alta demanda)
- 14-16 UTC (almoço Europa + acorda EUA)

**Coordenação entre projetos:** se você roda mais de um agente no mesmo
GitHub account, agende em horários diferentes para não brigarem pela mesma
fila do scheduler. Sugestão: cardiology = 04:17 UTC, music = 22:17 UTC.

## 4. iOS Safari intercepta `window.open`

PWA salvo na tela inicial e site servido via Safari/Chrome iOS abrem
`window.open('https://...')` num **SFSafariViewController** (in-app
browser estilo Safari) que **ignora a configuração "Default Browser"**.

**Solução:** scheme `googlechromes://` no iOS abre Chrome real.

Helper completo em `frontend/src/utils/openLink.js` do cardiology-agent. Resumo:

```js
function openInBrowser(url) {
  if (!isIOS()) { window.open(url, '_blank', 'noopener,noreferrer'); return; }
  // iOS: troca https:// por googlechromes:// (Chrome iOS responde a esse scheme)
  const chromeUrl = url.replace(/^https:\/\//, 'googlechromes://').replace(/^http:\/\//, 'googlechrome://');
  window.location.href = chromeUrl;
}

function handleExternalLinkClick(event, url) {
  // Para usar em <a target="_blank" @click.stop="handleExternalLinkClick($event, url)">
  if (!isIOS()) return; // deixa o browser nativo lidar
  event.preventDefault();
  openInBrowser(url);
}
```

Aplicar em **todos** os links externos dos cards.

## 5. NÃO force LLM a equilibrar fontes via regra numérica

**Erro do cardiology-agent (corrigido depois):** prompt do Pulso tinha
*"≥ min(N, total/2) destaques devem citar X"*. Resultado: Pulso escolhia
destaques só pra cumprir cota — qualidade caiu.

**Solução:** filtrar por **qualidade** das fontes ANTES, não forçar uso depois.

Para música: classifique fontes por **categoria** no fetch (ex: `categoria:
"critico_consagrado" | "blog_indie" | "newsletter" | "redes_sociais"`). No
prompt da síntese, oriente:
> "Priorize fontes categoria `critico_consagrado` e `blog_indie`. Use
> `redes_sociais` apenas como complemento quando reforça evidência primária."

Sem cota numérica. Deixa o LLM julgar.

## 6. Secrets NUNCA em arquivos do repo

- **Vite frontend:** apenas vars com prefixo `VITE_*`, em `.env.local` (no
  `.gitignore`). Exposto ao cliente — não use pra secrets reais.
- **GitHub Actions:** sempre `${{ secrets.NOME }}`. Adicionar via Settings →
  Secrets and variables → Actions.
- **Vercel:** env vars em Settings → Environment Variables. Pull local com
  `vercel env pull` para `.env.local`.

Se um token aparecer num chat ou commit acidental: **regere imediatamente**
o token (não basta deletar do commit).

## 7. Pipeline mínimo end-to-end ANTES de feature complexa

A ordem que funcionou no cardiology (e que faria melhor se tivesse seguido
desde o início):

1. **Skeleton:** 1 fonte → 1 LLM call → 1 arquivo JSON salvo localmente
2. **Frontend stub:** 1 página Vue que lê o JSON e mostra lista crua
3. **CI:** GitHub Actions workflow que roda o skeleton no cron
4. **Deploy:** Vercel projeto novo conectado ao repo
5. Só DEPOIS de tudo acima rodando organicamente: adicionar 2ª fonte, 3ª, etc

Adicionar fontes ao pipeline simples é fácil. Debugar um pipeline complexo
que nunca rodou inteiro é difícil.

## 8. Modelos LLM: separar tarefas por custo/capacidade

- **Classificação** (rápido, alto volume): use modelo barato
  (Haiku, Gemini Flash, GPT-4o-mini)
- **Síntese / Pulso** (julgamento, baixo volume): use modelo capaz
  (Sonnet, Gemini Pro, GPT-4o)
- **Discovery / pesquisa profunda** (raro, complexo): use modelo top
  (Opus, Gemini 2.5 Pro)

Cardiology-agent usa: Haiku para classify, Sonnet 4.6 para Pulso/post_ideas.
Custo total ~$0.30/run.

## 9. Cache fallback para LLM/API que pode falhar

Para fontes que falham com alguma frequência (xAI Grok deu 429 crônico por
3 dias seguidos no cardiology), tenha **cache fallback**:

```python
def fetch_x_posts():
    try:
        return live_fetch()  # tentativa normal com retries
    except Exception:
        logger.warning("Live fetch failed, using yesterday's cache")
        return _load_from_last_report_committed()  # lê do JSON commitado mais recente
```

Pior cenário: relatório de hoje repete dados de ontem nessa fonte específica
(marcado com flag `_cache_fallback: True` no JSON). Melhor que zerar.

## 10. Documentar decisões surpreendentes em comentários

Quando você toma uma decisão que parece estranha à primeira vista, comente
o **porquê**. Exemplo do cardiology:

```yaml
# grok-4 foi descontinuado em ~2026-05 — chamadas a esse modelo retornam
# 429 cronicamente (capacidade zero, sem aviso). grok-4.3 é o drop-in
# replacement oficial (mesmo preço, mesmas rate limits).
GROK_MODEL: ${{ vars.GROK_MODEL || 'grok-4.3' }}
```

Sem o comentário, o próximo Claude/dev mudaria para `grok-4` "limpando o
hardcoded" e quebraria tudo. Comentário explicativo = defesa contra
"refactor bem-intencionado mas errado".
