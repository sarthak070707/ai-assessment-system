import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import ThemeToggle from '../components/ThemeToggle.jsx'
import Footer from '../components/Footer.jsx'
import { api } from '../api.js'

/** Examiner portal, deliberately distinct from the candidate entrance. */
export default function AdminLogin() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  async function submit() {
    setBusy(true); setError('')
    try {
      await api.staffLogin(email.trim(), password)
      navigate('/')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  // No inverted panel: with two themes an inverted surface would be
  // white-on-white in one of them. The portals are told apart by their label and
  // their credential fields, which is the honest distinction anyway - the real
  // separation is require_staff on the server, not the paint.
  return (
    <div className="stack" style={{ minHeight: '100vh' }}>
      <div className="row" style={{ flex: 1, justifyContent: 'center', padding: '2rem' }}>
        <div style={{ width: '100%', maxWidth: 380 }}>
          <div className="spread">
            <Link to="/welcome" className="eyebrow" style={{ textDecoration: 'none' }}>← Back</Link>
            <ThemeToggle tone="quiet" />
          </div>
          <div style={{ height: '.6rem' }} />
          <span className="eyebrow" style={{ color: 'var(--ink-3)' }}>Staff access</span>
          <h1 style={{ marginTop: '.35rem' }}>Examiner portal</h1>
          <p className="small muted" style={{ marginTop: '.4rem', marginBottom: '1.5rem' }}>
            Question bank, assessment scheduling, exam codes and score review.
          </p>

          <div className="panel stack" style={{ padding: '1.25rem', gap: '.9rem' }}>
            <label className="stack" style={{ gap: '.3rem' }}>
              <span className="eyebrow">Institutional email</span>
              <input value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
            </label>
            <label className="stack" style={{ gap: '.3rem' }}>
              <span className="eyebrow">Password</span>
              <input
                type="password" value={password} autoComplete="current-password"
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && submit()}
              />
            </label>

            {error && (
              <div className="notice notice-alert">{error}</div>
            )}

            <button className="btn-primary" onClick={submit} disabled={busy}>
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
          </div>


        </div>
      </div>

      <Footer bordered={false} />
    </div>
  )
}
