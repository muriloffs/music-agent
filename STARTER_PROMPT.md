# Music Agent — Briefing inicial

> **Para o Claude que abrir este chat:** este documento é o ponto de partida.
> Leia também `PRINCIPIOS_HERDADOS.md`, `REFERENCIA_ARQUITETURAL.md` e
> `SETUP_TECNICO.md` antes de começar a codar. Discuta com o usuário as
> decisões marcadas como `<DEFINIR>` antes de qualquer implementação.

## O que é

Um agente **semanal** de música. A cada semana, varre fontes especializadas
de lançamentos, comentários e críticas, e entrega um relatório com:

- Lançamentos da semana que valem ouvir
- Comentários/contexto (de críticos, da cena, das redes)
- Recomendações filtradas para um curioso descobrindo

## Inspiração arquitetural

Replica os padrões dos projetos irmãos:
- **cardiology-agent** (cardiologia diária) — github.com/muriloffs/cardiology-agent
- **culture-agent** (filmes + música cultura geral) — projeto irmão

Princípios herdados em `PRINCIPIOS_HERDADOS.md`. Stack em `REFERENCIA_ARQUITETURAL.md`.

## Características já decididas

| Decisão | Valor |
|---|---|
| Frequência | **Semanal** (1 relatório/semana) |
| Público | **Eu mesmo / curioso descobrindo** (tom acessível, foca em "vale a pena ouvir?") |
| Idioma do output | PT-BR brasileiro |
| Tom | Acessível, explica referências, contextualiza artistas novos |
| Estilo de card | "Vale a pena? Por quê? Para quem?" — não review acadêmico |

## Decisões pendentes (primeira sessão deste chat)

| Decisão | Pendente | Observação |
|---|---|---|
| **Nicho musical específico** | `<DEFINIR>` | Pode ser combinação: ex "indie/alternativo internacional", "MPB + indie BR", "hip-hop/rap", "eletrônica", "jazz", "K-pop", "metal", "clássica", etc. **Decide isso primeiro** — define todas as fontes |
| Dia da semana do cron | `<DEFINIR>` | Sugestão: domingo cedo (relatório pronto pra leitura no fim de semana) ou sexta noite (preview pro fim de semana) |
| Nome final do projeto | `<DEFINIR>` | Default: `music-agent`. Pode ser temático conforme nicho (ex: `indie-radar`, `mpb-weekly`) |

## Diferenças relevantes do cardiology-agent

- **Frequência semanal vs diária** → 1 cron/semana em vez de 1/dia
- **Volume por run maior** → 7 dias de releases = mais conteúdo por run (estima ~50-150 lançamentos)
- **Sem urgência de "breaking news"** → não precisa atualizar várias vezes/dia
- **Custo total por mês muito menor** → ~$1-3/mês vs ~$10-15 do cardiology

## Restrições / não-objetivos (atualizar conforme chat decidir)

- Não inclui: `<DEFINIR — ex: shows ao vivo / vendas / charts / playlists genéricas>`
- Não recomenda: `<DEFINIR — ex: música que já é hit massivo, ja apareceu em 3+ semanas anteriores>`

## Primeira mensagem do chat dedicado

Quando abrir o chat novo, valide se o Claude leu todos os 4 docs. Depois
decida o nicho. Depois faça `curl` em pelo menos 1 fonte do nicho antes de
codificar qualquer linha (lição PMC do cardiology-agent — ver
PRINCIPIOS_HERDADOS).
