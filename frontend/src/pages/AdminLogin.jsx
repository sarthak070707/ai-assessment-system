import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
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

  return (
    <div style={{ minHeight: '100vh', background: 'var(--ink)' }}>
      <div className="row" style={{ minHeight: '100vh', justifyContent: 'center', padding: '2rem' }}>
        <div style={{ width: '100%', maxWidth: 380 }}>
          <Link to="/welcome" className="eyebrow" style={{ textDecoration: 'none', color: '#6B7480' }}>← Back</Link>
          <div style={{ height: '.6rem' }} />
          <span className="eyebrow" style={{ color: '#8C96A5' }}>Staff access</span>
          <h1 style={{ marginTop: '.35rem', color: '#fff' }}>Examiner portal</h1>
          <p className="small" style={{ color: '#8C96A5', marginTop: '.4rem', marginBottom: '1.5rem' }}>
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
              <div className="small" style={{
                color: 'var(--alert)', background: 'var(--alert-10)',
                border: '1px solid #EBC9C6', borderRadius: 'var(--r)', padding: '.5rem .65rem',
              }}>
                {error}
              </div>
            )}

            <button className="btn-primary" onClick={submit} disabled={busy}>
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
          </div>


        </div>
      </div>
    </div>
  )
}
