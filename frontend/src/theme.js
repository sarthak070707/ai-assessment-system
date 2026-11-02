/**
 * Theme state, held on the document element rather than in React.
 *
 * Applied outside React because index.html sets it before the bundle loads: a
 * theme decided during the first render flashes the wrong colours for a frame,
 * which on a dark-default app is a white strobe on every page load.
 */
const KEY = 'theme'

export function getTheme() {
  return document.documentElement.getAttribute('data-theme') || 'dark'
}

export function setTheme(theme) {
  const next = theme === 'light' ? 'light' : 'dark'
  document.documentElement.setAttribute('data-theme', next)
  document.documentElement.style.colorScheme = next
  try { localStorage.setItem(KEY, next) } catch { /* private browsing */ }
  return next
}

export function toggleTheme() {
  return setTheme(getTheme() === 'dark' ? 'light' : 'dark')
}
