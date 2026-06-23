# Ativar a "Playlist da semana" no Apple Music

A aba **▶️ Playlist** já está no site, mas fica inerte até a chave da Apple
entrar no servidor. Este guia é a parte que **só você** pode fazer (exige seu
Apple ID + cartão). Leva ~15 min, uma vez só.

Quando terminar, me avise — eu faço o deploy e a partir daí é um toque por
semana no seu iPhone.

---

## Visão geral

```
Apple Developer Program ($99/ano)
  └─ Media ID (identificador MusicKit)
       └─ Chave .p8  →  baixa UMA vez  →  3 valores:
            • Team ID         (10 chars)
            • Key ID          (10 chars)
            • conteúdo do .p8 (texto da chave privada)
                 ↓
            3 env vars na Vercel  →  deploy  →  botão funciona
```

---

## Passo 1 — Entrar no Apple Developer Program ($99/ano)

1. Acesse <https://developer.apple.com/programs/enroll/> logado com **seu Apple ID**.
2. Escolha **Individual** (pessoa física — mais simples; não precisa de empresa).
3. Pague os **US$ 99** (renova anual; pode cancelar quando quiser).
4. A aprovação costuma sair em minutos a poucas horas.

> A conta é vinculada ao seu Apple ID — é o que prova que o app é seu. Sem isso
> a Apple não emite a chave.

## Passo 2 — Anotar o Team ID

1. Vá em <https://developer.apple.com/account> → **Membership details**.
2. Copie o **Team ID** (10 caracteres, ex.: `A1B2C3D4E5`). Guarde.

## Passo 3 — Criar o Media ID (identificador MusicKit)

1. Em **Certificates, Identifiers & Profiles** → **Identifiers** → botão **+**.
2. Escolha **Media IDs** → Continue.
3. Description: `Music Agent`. Identifier: `media.com.muriloffs.musicagent`
   (qualquer coisa única; o prefixo `media.` é exigido). → Continue → Register.

## Passo 4 — Criar a chave MusicKit (.p8)

1. Em **Keys** → botão **+** (Create a key).
2. Key Name: `Music Agent MusicKit`.
3. Marque **MusicKit** na lista de serviços → **Configure** → selecione o Media
   ID criado no passo 3 → Save.
4. Continue → **Register**.
5. **Baixe o arquivo `.p8`** (botão Download). ⚠️ **Só dá pra baixar UMA vez** —
   se perder, tem que criar outra chave. Guarde num lugar seguro.
6. Anote o **Key ID** mostrado na página (10 caracteres).

## Passo 5 — Me mandar os 3 valores (em particular)

Me passe:

| Valor | Onde está |
|---|---|
| **Team ID** | passo 2 |
| **Key ID** | passo 4, item 6 |
| **Conteúdo do .p8** | abra o arquivo num editor de texto e copie tudo, incluindo as linhas `-----BEGIN PRIVATE KEY-----` e `-----END PRIVATE KEY-----` |

> O `.p8` é uma **chave privada** — trate como senha. Não cole em chat público,
> issue, nem commit. Vai direto pras env vars da Vercel (criptografadas).

## Passo 6 — (eu faço) Plugar na Vercel

No painel da Vercel → projeto → **Settings → Environment Variables**, adiciono:

| Nome | Valor |
|---|---|
| `APPLE_TEAM_ID` | seu Team ID |
| `APPLE_KEY_ID` | seu Key ID |
| `APPLE_PRIVATE_KEY` | conteúdo do .p8 |

Um **redeploy** e a edge function `/api/musickit-token` passa a assinar o
Developer Token. O botão na aba ▶️ Playlist sai do estado "ainda não ativado".

---

## Como fica no dia a dia

```
sábado     → o pipeline gera o relatório (já acontece)
você abre  → o site no iPhone → aba ▶️ Playlist
toca       → "Criar no Apple Music" → autoriza com sua conta (1ª vez só)
pronto     → playlist "Music Agent — DD/mês" na sua biblioteca Apple Music
```

## Custos

- **US$ 99/ano** — Apple Developer Program (único custo).
- A API da Apple Music em si é **grátis** dentro do programa.
- Não cobra por playlist criada nem por faixa.

## Notas técnicas

- O Developer Token (JWT) é assinado **no servidor** com a chave privada
  (`api/musickit-token.js`), válido 180 dias, e cacheado na borda. A chave `.p8`
  nunca chega ao navegador.
- A criação da playlist roda **no navegador** via MusicKit JS, porque exige o
  *Music User Token* — que só se obtém com você autorizando interativamente.
  Por isso não dá pra criar a playlist sozinho no cron do GitHub Actions.
- Storefront BR: no teste com o relatório de 20/jun, **36 de 37** faixas com
  link existiam no catálogo brasileiro (a 1 ausente é simplesmente pulada).
