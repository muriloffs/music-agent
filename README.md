# Music Agent

Agente semanal de música — varre fontes especializadas de lançamentos, comentários e críticas, e entrega um relatório curado para um curioso descobrindo.

## Status

🚧 **Em planejamento.** Implementação ainda não começou — apenas docs de design.

## Estrutura prevista

```
music-agent/
├── agent/            # Pipeline Python (orquestrador + fetchers + LLM)
├── api/              # Vercel functions (serve o JSON)
├── data/             # Relatórios semanais commitados (JSON)
├── frontend/         # Vue 3 + Vite + Tailwind
└── .github/workflows # Cron semanal
```

## Documentos de planejamento

Leia nesta ordem antes de começar:

1. [`STARTER_PROMPT.md`](STARTER_PROMPT.md) — briefing inicial
2. [`PRINCIPIOS_HERDADOS.md`](PRINCIPIOS_HERDADOS.md) — 10 lições do projeto irmão (cardiology-agent)
3. [`REFERENCIA_ARQUITETURAL.md`](REFERENCIA_ARQUITETURAL.md) — stack proposta + schema + cron sugerido
4. [`SETUP_TECNICO.md`](SETUP_TECNICO.md) — APIs + secrets + checklist de validação

## Projetos irmãos

- [cardiology-agent](https://github.com/muriloffs/cardiology-agent) — agente diário de cardiologia (referência arquitetural)
- culture-agent — agente de filmes + música cultura geral (planejado)
