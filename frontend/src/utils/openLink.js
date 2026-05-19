// openLink.js — iOS Safari workaround (cardiology-agent lesson 4)
//
// Why: PWA on iOS home screen + Safari in-app browser ignores user's
// "Default Browser" setting and forces SFSafariViewController. Using
// `googlechromes://` scheme opens the real Chrome on iOS.

function isIOS() {
  if (typeof navigator === 'undefined') return false
  return /iPad|iPhone|iPod/.test(navigator.userAgent)
}

export function openInBrowser(url) {
  if (!url) return
  if (!isIOS()) {
    window.open(url, '_blank', 'noopener,noreferrer')
    return
  }
  const chromeUrl = url
    .replace(/^https:\/\//, 'googlechromes://')
    .replace(/^http:\/\//, 'googlechrome://')
  window.location.href = chromeUrl
}

export function handleExternalLinkClick(event, url) {
  if (!isIOS()) return
  event.preventDefault()
  openInBrowser(url)
}
