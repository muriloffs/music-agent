# Setup técnico — Music Agent

> Tudo que precisa estar configurado antes do primeiro `git push origin main`.
> Marcar `[x]` quando feito.

## Ferramentas locais (já instaladas pelo projeto irmão)

Estas estão prontas na sua máquina Windows (vêm do cardiology-agent):

- [x] `gh` CLI autenticado (GitHub) — `~/bin/gh` wrapper
- [x] `vercel` CLI autenticado — `~/bin/vercel` wrapper (com `NODE_OPTIONS=--use-system-ca`)
- [x] `jq` para parsing JSON
- [x] Python 3.11 / Node.js / npm

Verificar funcionando:

```bash
gh auth status
vercel whoami
jq --version
python --version
node --version
```

## Repositório GitHub

- [ ] Criar repo público novo: `muriloffs/music-agent` (ou outro nome)
  - **Por que público:** GitHub Actions é grátis em repos públicos (minutes ilimitados)
- [ ] `git init` local na pasta + primeiro commit com README + estes 4 docs
- [ ] `git remote add origin <url>` + push inicial
- [ ] Habilitar GitHub Actions (Settings → Actions → General → Allow all actions)
- [ ] Settings → Actions → General → Workflow permissions → **Read and write**
  (sem isso, o workflow não consegue commitar o JSON do relatório)

## Secrets do GitHub Actions (Settings → Secrets → Actions)

Conforme o nicho e LLMs escolhidos, configurar APENAS o que vai usar:

- [ ] `ANTHROPIC_API_KEY` (se usar Claude) — console.anthropic.com
- [ ] `GOOGLE_API_KEY` (se usar Gemini) — aistudio.google.com
- [ ] `OPENAI_API_KEY` (se usar GPT) — platform.openai.com
- [ ] `SPOTIFY_CLIENT_ID` + `SPOTIFY_CLIENT_SECRET` (se usar Spotify Web API)
- [ ] `LASTFM_API_KEY` (se usar Last.fm)
- [ ] `GENIUS_ACCESS_TOKEN` (se usar Genius)
- [ ] `<outras conforme nicho>`

## Vercel

- [ ] Importar projeto no Vercel (vercel.com/new)
- [ ] Settings → Environment Variables: copiar os mesmos secrets do GitHub
  para `Production` (Vercel functions vão precisar)
- [ ] Settings → Domains: domínio padrão `<nome>.vercel.app` está OK pra começar

## APIs externas — checklist de validação (FAZER ANTES DE CODAR)

> **Para cada API que vai integrar, preencha esta tabela ANTES de escrever
> linha de código.** Lição PMC do cardiology-agent: 30 segundos de `curl`
> antes evitam dias de retrabalho.

| API | Rate limit | Custo | Auth necessária | Validei com `curl`? |
|---|---|---|---|---|
| <API 1: ex Pitchfork RSS> | <X req/s> | <$> | nenhum/key/oauth | ⬜ |
| <API 2: ex Spotify Web API> | 180 req/min | grátis | OAuth2 client_credentials | ⬜ |
| <API 3: ex Last.fm> | 5 req/s | grátis | api_key | ⬜ |
| <API 4: ex Genius> | 1 req/s | grátis | bearer token | ⬜ |
| <API 5> | ... | ... | ... | ⬜ |

### Template de validação `curl`

```bash
# 1. Confirmar que API retorna formato esperado
curl -sL "https://api.exemplo.com/endpoint" | jq . | head -50

# 2. Confirmar volume típico
curl -sL "https://api.exemplo.com/endpoint" | jq 'length'

# 3. Confirmar campos críticos existem
curl -sL "https://api.exemplo.com/endpoint" | jq '.[0] | keys'

# 4. Para feeds RSS: confirmar estrutura
curl -sL "https://pitchfork.com/rss/reviews/best/albums/" | head -50
```

### Critérios go/no-go para integrar uma API

Antes de codificar fetcher dela:
- ✅ Retorna dado relevante para meu nicho (não só dado tangencial)
- ✅ Tem volume útil na frequência semanal (≥5 itens por semana)
- ✅ Auth viável (gratuito ou ≤$5/mês ou nenhuma)
- ✅ Rate limit confortável para 1 run/semana (com folga 10x)
- ✅ Latência aceitável (resposta em <30s)

Se algum desses falhar → procurar fonte alternativa. Não force integração de
fonte ruim.

## Estrutura inicial mínima (criar nesta ordem)

### Sessão 1 do chat dedicado

```
music-agent/
├── README.md
├── .gitignore
├── STARTER_PROMPT.md           # já existe
├── PRINCIPIOS_HERDADOS.md      # já existe
├── REFERENCIA_ARQUITETURAL.md  # já existe
├── SETUP_TECNICO.md            # já existe
└── agent/
    └── scripts/
        └── fetch_<fonte_1>.py  # 1 fonte, validada antes
```

### Sessão 2: pipeline mínimo

Adicionar `agent/agent.py`, `agent/parser.py`, `agent/prompt.txt` (cópias
simplificadas do cardiology), `data/.gitkeep`. Primeiro relatório salvo
localmente.

### Sessão 3: CI + frontend mínimo

Adicionar `.github/workflows/weekly-report.yml`, `vercel.json`,
`frontend/` (skeleton Vue + Vite), `api/report.js`.

## `.gitignore` recomendado

```
# Python
__pycache__/
*.pyc
.pytest_cache/
.venv/
venv/

# Node
node_modules/
.npm/

# Build outputs
dist/
build/
.next/

# Env secrets
.env
.env.local
.env.*.local

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/

# Vercel
.vercel

# Logs
*.log
```

## Comandos úteis (referência rápida para sessões futuras)

```bash
# Disparar workflow manualmente (depois de configurar GH Actions)
gh workflow run weekly-report.yml -R muriloffs/music-agent

# Acompanhar último run
gh run watch -R muriloffs/music-agent

# Ler logs de run com erro
gh run view <run-id> -R muriloffs/music-agent --log-failed

# Ver últimos deploys Vercel
vercel ls

# Logs do último deploy
vercel logs cardiology-agent  # ajustar nome do projeto

# Pull env vars do Vercel para .env.local
vercel env pull

# Build + test do frontend
cd frontend && npm install && npm run build
```

## Notas finais

- **Não copiar código do cardiology cegamente.** Releia e adapte — alguns
  patterns são específicos do domínio cardiológico.
- **`openLink.js` é uma das poucas coisas que vale copiar verbatim** —
  resolve um bug iOS que vai aparecer aqui também.
- **Schemas de output vão evoluir** — o primeiro JSON salvo provavelmente
  vai mudar 3-4x antes de estabilizar. Não otimize cedo.
