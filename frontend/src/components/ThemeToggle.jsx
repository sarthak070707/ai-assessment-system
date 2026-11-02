import { useState } from 'react'
import { getTheme, toggleTheme } from '../theme.js'

/** Sun or moon, showing the theme you would switch *to*. */
export default function ThemeToggle({ tone = 'default' }) {
  const [theme, setThemeState] = useState(getTheme)
  const dark = theme === 'dark'

  return (
    <button
      onClick={() => setThemeState(toggleTheme())}
      aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={dark ? 'Light mode' : 'Dark mode'}
      className="btn-ghost"
      style={{
        padding: '.4rem', lineHeight: 0, borderRadius: 'var(--r)',
        borderColor: tone === 'quiet' ? 'transparent' : 'var(--rule)',
        color: 'var(--ink-2)',
      }}
    >
      {dark ? (
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="4.2" stroke="currentColor" strokeWidth="1.7" />
          <path d="M12 2.6v2.2M12 19.2v2.2M2.6 12h2.2M19.2 12h2.2M5.4 5.4l1.6 1.6M17 17l1.6 1.6M18.6 5.4L17 7M7 17l-1.6 1.6"
                stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
        </svg>
      ) : (
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M20.5 14.2A8.5 8.5 0 1 1 9.8 3.5a6.8 6.8 0 0 0 10.7 10.7Z"
                stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
        </svg>
      )}
    </button>
  )
}
