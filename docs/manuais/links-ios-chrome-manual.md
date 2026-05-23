# Manual: Abrir links no Chrome (ou app nativo) em iOS

> Compartilhe este arquivo com outros agentes (culture, music-agent, etc.)
> que tenham frontend com links externos clicados por usuários de iPhone/iPad.
> Reproduz a feature implementada no cardiology-agent em commits
> `124cb4b` + `2779673` (escape SFSafariViewController) e refinada em uma
> commit posterior (exceção para apps fortes).

## O problema

No iOS, quando uma página web faz `window.open('https://...', '_blank')` ou
o usuário clica em `<a target="_blank">`, o sistema operacional frequentemente
**rotea a navegação por uma SFSafariViewController** — um "in-app browser"
que parece o Safari mas:

1. **Ignora a configuração "Default Browser"** do iOS. Mesmo que o usuário
   tenha o Chrome (ou Firefox, Edge) definido como padrão, o link abre nessa
   sheet com cara de Safari.
2. **Não compartilha sessão, cookies, abas, histórico** com o navegador real
   do usuário.
3. **É mais difícil de "promover" pra uma aba real** — o botão "bússola" no
   canto inferior abre no default browser, mas a maioria dos usuários nem
   sabe que ele faz isso.

Esse comportamento é forçado pelo iOS principalmente em **PWAs salvos na tela
inicial** e em sites servidos via Safari. Para um dashboard pessoal usado
diariamente no celular, é uma fonte constante de fricção.

## A solução em uma frase

Roteia HTTPS via esquema `googlechromes://` no iOS — o Chrome iOS registra
esse esquema e o sistema abre o app real, sem passar pela in-app sheet.
**Exceções:** domínios com apps nativos fortes (YouTube, Spotify, X, Apple
Podcasts) usam `window.open` puro pra deixar o iOS Universal Links abrir o
app correspondente.

## Quando aplicar

Você tem essa necessidade se **todos** se aplicam:

1. Frontend tem **muitos links externos** (cards com botão "Ler", "Ver post",
   "Ouvir", etc.).
2. Os usuários acessam principalmente por **iPhone ou iPad**.
3. O site é frequentemente acessado via **PWA salvo na tela inicial** OU via
   Safari (não via Chrome — se for via Chrome, o problema é menor).
4. Usuários reclamaram (ou reclamariam se notassem) que links abrem num
   browser estranho com "✕" no canto e bússola embaixo.

## Decisões de design (e o porquê de cada uma)

### 1. **Só interceptar em iOS** — desktop e Android ficam intocados

Desktop tem zoom, Ctrl+Click, middle-click — manipulação do click via JS
quebraria isso. Android respeita o default browser de forma confiável. O
problema é específico de iOS. Por isso `if (!isIOS()) return` no helper.

### 2. **Hardcoded list de domínios "app-preferred", não heurística**

Em vez de tentar adivinhar quais domínios têm Universal Links registrados
(impossível com confiança), mantemos uma lista curta e explícita: YouTube,
Spotify, X, Apple Podcasts. Lista é pequena (~10 hosts), revisável,
auditável. Heurística teria risco de surpresa (link de blog pessoal abrir
um app aleatório).

### 3. **`googlechromes://` (com `s` final) para HTTPS** — `googlechrome://` para HTTP

O Chrome iOS registra os dois esquemas separados. URL HTTPS vira `googlechromes://`
(com `s`); HTTP vira `googlechrome://` (sem `s`). Errar o `s` resulta em iOS
recusar a navegação. Documentado em
https://developer.chrome.com/docs/multidevice/ios/links/

### 4. **Fallback de 600ms** quando Chrome não está instalado

Se o usuário não tem Chrome no iPhone, navegar para `googlechromes://...`
faz iOS recusar silenciosamente — a página fica visível. Setamos um timer
de 600ms: se a página ainda está visível depois disso, fazemos `window.open`
com a URL original. Usuário ainda navega para algum lugar (não bom, mas não
quebrado). Usuários do agente que confirmaram ter Chrome instalado nunca
sentem isso.

### 5. **Click handler em `<a target="_blank">`** preserva semântica HTML

Não trocamos `<a>` por `<button>` com `@click`. Mantemos `<a href target="_blank"
rel="noopener noreferrer">` e adicionamos `@click` que só atua em iOS:
- **iOS:** `event.preventDefault()` + chama o helper Chrome scheme
- **Outras plataformas:** no-op (browser nativo lida)

Vantagens: leitores de tela anunciam corretamente como link; long-press no
iPhone abre menu nativo com "Open in [default browser]" + "Copy" + "Share";
Ctrl+Click/middle-click no desktop seguem funcionando.

## Arquitetura

```
┌──────────────────────────────────────┐
│ <a href="..." target="_blank"        │
│    rel="noopener noreferrer"         │
│    @click.stop="handleClick($event)">│
│   🔗 Ler                              │
└──────────────────────────────────────┘
                  │ click
                  ▼
┌──────────────────────────────────────┐
│ handleExternalLinkClick(event, url)  │
│   if (!isIOS()) return; // no-op     │
│   event.preventDefault();            │
│   openInBrowser(url)                 │
└────────────────┬─────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────┐
│ openInBrowser(url)                   │
│   if (!isIOS()) window.open()        │
│   if (shouldPreferNativeApp(url))    │
│     window.open()  // Universal Link │
│   else                                │
│     window.location = chromeScheme   │
│     setTimeout(fallback, 600ms)      │
└──────────────────────────────────────┘
```

## Implementação — 1 arquivo + edits em N cards

### `frontend/src/utils/openLink.js` (helper completo)

```js
/**
 * Open external URLs honoring the user's preferred browser on iOS.
 * Two-tier strategy:
 *  1. App-preferred hosts (YouTube etc) → window.open (Universal Links)
 *  2. Everything else https/http → googlechromes:// scheme (Chrome iOS)
 * Other platforms (desktop, Android) get standard window.open.
 */

function isIOS() {
  if (typeof navigator === 'undefined') return false
  const ua = navigator.userAgent || ''
  if (/iPad|iPhone|iPod/.test(ua)) return true
  // iPadOS 13+ reports as Mac in UA; touch points as fallback
  return navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1
}

function toChromeScheme(url) {
  if (url.startsWith('https://')) return 'googlechromes://' + url.slice(8)
  if (url.startsWith('http://')) return 'googlechrome://' + url.slice(7)
  return null
}

// Domínios cujo app nativo provê experiência estritamente melhor que browser.
// Lista hardcoded > heurística: explícita, auditável, sem surpresas.
const APP_PREFERRED_HOSTS = new Set([
  // YouTube — opens YouTube app (player nativo, PiP, áudio em background)
  'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be', 'music.youtube.com',
  // Spotify — opens Spotify app (player, podcasts)
  'open.spotify.com',
  // Apple Podcasts — opens Podcasts app
  'podcasts.apple.com',
  // X/Twitter — opens X app (threading, conta logada)
  'twitter.com', 'www.twitter.com', 'x.com', 'www.x.com', 'mobile.twitter.com',
  // WhatsApp — opens WhatsApp app (mensagens, grupos, shortlinks wa.me)
  'wa.me', 'whatsapp.com', 'www.whatsapp.com', 'chat.whatsapp.com', 'api.whatsapp.com',
  // Things 3 (defensivo — uso primário é deeplink things://, ver nota abaixo)
  'culturedcode.com', 'www.culturedcode.com',
])

// NOTA IMPORTANTE: deeplinks de app (`things:///add?...`, `whatsapp://...`,
// `spotify://...`, `tg://...`, `mailto:`, `tel:`) NÃO precisam estar nesta
// lista. Eles já passam direto pelo fallback `if (!chromeUrl) window.open(...)`
// no openInBrowser, porque `toChromeScheme` só converte http(s) e retorna
// null pra outros esquemas. O iOS faz o roteamento pro app correspondente
// automaticamente quando o esquema é registrado por um app instalado.
// Esta lista é para URLs HTTPS de sites que TAMBÉM têm app forte instalado.

function shouldPreferNativeApp(url) {
  try {
    return APP_PREFERRED_HOSTS.has(new URL(url).hostname.toLowerCase())
  } catch {
    return false
  }
}

export function openInBrowser(url) {
  if (!url || typeof url !== 'string') return

  // Não-iOS: padrão é suficiente — default browser e modificadores funcionam
  if (!isIOS()) {
    window.open(url, '_blank', 'noopener,noreferrer')
    return
  }

  // Exceção 1: app-preferred hosts — deixa iOS Universal Links rotear
  if (shouldPreferNativeApp(url)) {
    window.open(url, '_blank', 'noopener,noreferrer')
    return
  }

  // Exceção 2: esquemas não-http(s) (mailto:, tel:, app://) — passa direto
  const chromeUrl = toChromeScheme(url)
  if (!chromeUrl) {
    window.open(url, '_blank', 'noopener,noreferrer')
    return
  }

  // Caminho principal: HTTPS/HTTP → Chrome scheme. Se Chrome não instalado,
  // fallback após 600ms (página ainda visível = navegação foi recusada)
  const start = Date.now()
  window.location.href = chromeUrl
  setTimeout(() => {
    if (Date.now() - start < 1500 && !document.hidden) {
      window.open(url, '_blank', 'noopener,noreferrer')
    }
  }, 600)
}

/**
 * Click handler para <a target="_blank">. Em iOS intercepta e roteia via
 * openInBrowser; em outras plataformas, no-op (preserva Ctrl+Click etc).
 */
export function handleExternalLinkClick(event, url) {
  if (!url) return
  if (!isIOS()) return // browser nativo lida
  if (event) event.preventDefault()
  openInBrowser(url)
}
```

### Em CADA card com link externo

Padrão de markup (mantém `<a>` semântico):

```vue
<a
  :href="article.links.url"
  target="_blank"
  rel="noopener noreferrer"
  class="seu-estilo"
  @click.stop="handleExternalLinkClick($event, article.links.url)"
>
  🔗 Ler
</a>
```

Padrão de script:

```js
import { handleExternalLinkClick } from '../utils/openLink'
// (não precisa criar variável — passa direto pro template)
```

E para "click no card inteiro" (não `<a>`):

```vue
<div @click="openInBrowser(article.links.url)">...</div>
```

```js
import { openInBrowser } from '../utils/openLink'
```

## Detalhes que importam

1. **`event.preventDefault()` SÓ em iOS.** Em desktop, `preventDefault` em
   `@click` cancela Ctrl+Click/middle-click. O `if (!isIOS()) return` evita.

2. **`@click.stop`** evita propagar o click pra um possível handler de
   "click no card todo". Cards têm múltiplos elementos clicáveis e a
   propagação default abre dois fluxos ao mesmo tempo.

3. **Manter `target="_blank" rel="noopener noreferrer"`** mesmo com o handler
   JS. Em non-iOS o browser usa esses atributos diretamente.

4. **Fallback de 600ms** detecta "Chrome não instalado" via `document.hidden`.
   Se Chrome abriu, a página vai pra background → `document.hidden = true`
   → não dispara o fallback. Se Chrome não abriu, página segue visível →
   fallback abre via `window.open`. Não é determinístico (pode haver race
   conditions raras), mas funciona em 99% dos casos práticos.

5. **`APP_PREFERRED_HOSTS` é um `Set`** — lookup `O(1)` por hostname.
   `URL().hostname` já normaliza pra lowercase no parsing (mas defesa em
   profundidade aplicando `.toLowerCase()` mesmo assim — alguns navegadores
   antigos não normalizam).

## Anti-padrões a evitar

| ❌ Anti-padrão | ✅ Por quê não |
|---|---|
| Trocar `<a>` por `<button>` com `@click` | Quebra acessibilidade, long-press do iOS, Ctrl+Click |
| `event.preventDefault()` sempre (não só iOS) | Quebra Ctrl+Click/middle-click no desktop |
| Detectar Chrome instalado antes de tentar | Não há API pública pra isso no iOS — o fallback de 600ms é a melhor heurística |
| Heurística pra "domínios com app" | Falsos positivos abrem apps aleatórios; lista hardcoded é mais segura |
| Esquecer o `s` em `googlechromes://` (HTTPS) | iOS recusa navegação silenciosamente |
| Aplicar em desktop também | `preventDefault` cancela modificadores; problema só existe em iOS |
| Detectar iOS por user-agent só pelo `iPhone` | iPadOS 13+ se reporta como Mac; precisa do check de `maxTouchPoints` |
| `target="_self"` (mesma aba) | Perde a aba do dashboard; sempre `_blank` |

## YAGNI deliberados

- **Settings/toggle pra usuário escolher "abrir no Chrome ou no Safari"** —
  ninguém quer essa configuração; quem instalou Chrome quer Chrome.
- **Detectar versão do Chrome iOS / fallback pra Firefox** — projeto não
  tem usuários em volume suficiente pra justificar.
- **Auto-detectar Universal Links registrados** — API não existe; lista
  hardcoded resolve.
- **Logar/medir quantos links foram redirecionados** — métrica sem ação.

## Custo de implementação

- ~30 min: 1 arquivo helper + edits em todos os cards do projeto
- ~150 linhas de JS + edits curtos por card (1 import + `@click` em cada `<a>`)
- **Custo de tokens LLM: zero** — feature 100% frontend client-side
- Build sem mudança (compilação Vite igual)

## Como testar

1. **Antes de testar:** force-refresh ou aba anônima no iPhone (cache do JS antigo).
2. Abre o dashboard.
3. Clica num botão "Ler" de um card de artigo (não de YouTube).
4. **Esperado:** abre o Chrome real (com a interface do Chrome — sem o `✕`
   no canto superior esquerdo da SFSafariViewController).
5. Volta e clica num botão de assistir vídeo do YouTube (se aplicável).
6. **Esperado:** abre o app YouTube nativo (não o Chrome, não a in-app sheet).
7. Se em algum caso ainda abrir a in-app sheet com `✕` e bússola embaixo,
   tem algum link que ainda usa `<a>` puro sem o handler — auditar.

## Commit de referência (no cardiology-agent)

- `124cb4b` — fix iOS Chrome scheme (helper inicial em App.vue's openArticle/openPodcast)
- `2779673` — estende para todos os botões "Ler" dos cards
- Commit posterior — adiciona `APP_PREFERRED_HOSTS` (esta exceção)

## Manual irmão

- `docs/manuais/modo-leitura-mobile-manual.md` — feature complementar de
  "Modo Leitura" para cards com texto editorial denso no mobile (do culture-agent).
