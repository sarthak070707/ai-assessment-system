import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, getUser } from '../api.js'

/** Shown when an account is still on the temporary password issued by the exam office. */
export default function SetPassword() {
  const user = getUser()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  async function submit() {
    setError('')
    if (next !== confirm) return setError('The two new passwords do not match.')
    if (next.length < 8) return setError('Choose a password of at least 8 characters.')
    setBusy(true)
    try {
      await api.changePassword(current, next)
      const stored = { ...user, must_change_password: false }
      localStorage.setItem('user', JSON.stringify(stored))
      navigate('/')
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--ink)' }}>
      <div className="row" style={{ minHeight: '100vh', justifyContent: 'center', padding: '2rem' }}>
        <div style={{ width: '100%', maxWidth: 400 }}>
          <span className="eyebrow" style={{ color: '#8C96A5' }}>First sign-in</span>
          <h1 style={{ marginTop: '.35rem', color: '#fff' }}>Choose your password</h1>
          <p className="small" style={{ color: '#8C96A5', marginTop: '.4rem', marginBottom: '1.5rem' }}>
            Your account was issued with a temporary password that the exam office also knows.
            Replace it before you can use the portal.
          </p>

          <div className="panel stack" style={{ padding: '1.25rem', gap: '.9rem' }}>
            <label className="stack" style={{ gap: '.3rem' }}>
              <span className="eyebrow">Temporary password</span>
              <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" />
            </label>
            <label className="stack" style={{ gap: '.3rem' }}>
              <span className="eyebrow">New password</span>
              <input type="password" value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" />
            </label>
            <label className="stack" style={{ gap: '.3rem' }}>
              <span className="eyebrow">Confirm new password</span>
              <input
                type="password" value={confirm} autoComplete="new-password"
                onChange={(e) => setConfirm(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && submit()}
              />
            </label>

            {error && (
              <div className="small" style={{ color: 'var(--alert)', background: 'var(--alert-10)', border: '1px solid #EBC9C6', borderRadius: 'var(--r)', padding: '.5rem .65rem' }}>
                {error}
              </div>
            )}

            <button className="btn-primary" onClick={submit} disabled={busy}>
              {busy ? 'Saving…' : 'Set password and continue'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
