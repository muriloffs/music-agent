// openLink.js — open external URLs honoring the user's preferred browser on iOS.
//
// Why: PWA on iOS home screen + Safari in-app browser ignores user's "Default
// Browser" setting and forces SFSafariViewController. Routing https:// via
// `googlechromes://` opens the real Chrome instead.
//
// Two-tier strategy (see docs/manuais/links-ios-chrome-manual.md):
//   1. App-preferred hosts (YouTube, Spotify, Apple Music, WhatsApp, X,
//      Bandcamp, Apple Podcasts) → window.open lets iOS Universal Links
//      route to the native app — strictly better experience than Chrome.
//   2. Everything else https/http → googlechromes:// scheme.
//   3. Custom schemes (mailto:, things:///, etc.) → falls through to
//      window.open as last resort; for Things deep-links the caller should
//      keep a plain <a href> and skip this handler entirely.
//
// Other platforms (desktop, Android) get standard window.open — desktop's
// Ctrl/middle-click modifiers must keep working, so we never preventDefault
// outside iOS.

function isIOS() {
  if (typeof navigator === 'undefined') return false
  const ua = navigator.userAgent || ''
  if (/iPad|iPhone|iPod/.test(ua)) return true
  // iPadOS 13+ reports as Mac in the UA; the touch-points check disambiguates.
  return navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1
}

function toChromeScheme(url) {
  if (url.startsWith('https://')) return 'googlechromes://' + url.slice(8)
  if (url.startsWith('http://')) return 'googlechrome://' + url.slice(7)
  return null
}

// Domains whose native app gives a strictly better experience than any
// browser. Hardcoded > heuristic: explicit, auditable, no surprises (a blog
// link would never accidentally open an unrelated app). Music-agent-specific
// additions vs. the base manual: Apple Music, Bandcamp.
const APP_PREFERRED_HOSTS = new Set([
  // YouTube — opens YouTube app (native player, PiP, background audio)
  'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be', 'music.youtube.com',
  // Spotify — opens Spotify app (player, podcasts)
  'open.spotify.com',
  // Apple Music — opens Music app
  'music.apple.com',
  // Apple Podcasts — opens Podcasts app
  'podcasts.apple.com',
  // Bandcamp — opens Bandcamp app on iOS
  'bandcamp.com',
  // WhatsApp — opens WhatsApp app (messages, groups, wa.me shortlinks)
  'wa.me', 'whatsapp.com', 'www.whatsapp.com', 'chat.whatsapp.com', 'api.whatsapp.com',
  // X/Twitter — opens X app (threading, logged-in account)
  'twitter.com', 'www.twitter.com', 'x.com', 'www.x.com', 'mobile.twitter.com',
  // Things 3 (defensive — primary use is the things:// deeplink, see note below)
  'culturedcode.com', 'www.culturedcode.com',
])

// IMPORTANT: app deeplinks (`things:///add?...`, `whatsapp://...`, `spotify://...`,
// `tg://...`, `mailto:`, `tel:`) do NOT need to be in APP_PREFERRED_HOSTS.
// They already pass straight through the `if (!chromeUrl) window.open(...)`
// branch in openInBrowser, because toChromeScheme only converts http(s) and
// returns null for other schemes. iOS routes to the registered app
// automatically when the scheme is registered by an installed app.
// APP_PREFERRED_HOSTS is for HTTPS URLs of sites that ALSO have a strong app.

function shouldPreferNativeApp(url) {
  try {
    return APP_PREFERRED_HOSTS.has(new URL(url).hostname.toLowerCase())
  } catch {
    return false
  }
}

export function openInBrowser(url) {
  if (!url || typeof url !== 'string') return

  // Non-iOS: the OS already respects the user's default browser, and modifier
  // clicks (Ctrl/middle) must keep working — never intercept here.
  if (!isIOS()) {
    window.open(url, '_blank', 'noopener,noreferrer')
    return
  }

  // App-preferred hosts: let iOS Universal Links route to the native app.
  if (shouldPreferNativeApp(url)) {
    window.open(url, '_blank', 'noopener,noreferrer')
    return
  }

  // Non-http(s) schemes (mailto:, tel:, etc.) — Chrome scheme rewrite makes
  // no sense here; pass straight through.
  const chromeUrl = toChromeScheme(url)
  if (!chromeUrl) {
    window.open(url, '_blank', 'noopener,noreferrer')
    return
  }

  // Main path: HTTPS/HTTP → real Chrome on iOS. If Chrome isn't installed,
  // iOS silently refuses the navigation and the page stays visible; the
  // 600ms timer detects that (document.hidden would be true if Chrome
  // had backgrounded us) and falls back to window.open.
  const start = Date.now()
  window.location.href = chromeUrl
  setTimeout(() => {
    if (Date.now() - start < 1500 && !document.hidden) {
      window.open(url, '_blank', 'noopener,noreferrer')
    }
  }, 600)
}

// Click handler for <a target="_blank">. Only acts on iOS — every other
// platform's anchor semantics already do the right thing (default browser,
// modifier clicks, screen-reader announcement, long-press menu).
export function handleExternalLinkClick(event, url) {
  if (!url) return
  if (!isIOS()) return
  if (event) event.preventDefault()
  openInBrowser(url)
}
