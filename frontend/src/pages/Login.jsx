import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import ThemeToggle from '../components/ThemeToggle.jsx'
import Footer from '../components/Footer.jsx'
import { api } from '../api.js'

/** Candidate portal. Enrolment number plus the single-use code for today's paper. */
export default function Login() {
  const [enrollment, setEnrollment] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  async function submit() {
    if (!enrollment.trim() || !code.trim()) {
      return setError('Enter both your enrolment number and the exam code.')
    }
    setBusy(true); setError('')
    try {
      await api.examLogin(enrollment.trim(), code.trim())
      navigate('/')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack" style={{ minHeight: '100vh' }}>
      <div className="row" style={{ flex: 1, justifyContent: 'center', padding: '2rem' }}>
      <div style={{ width: '100%', maxWidth: 400 }}>
        <div className="spread">
          <Link to="/welcome" className="eyebrow" style={{ textDecoration: 'none' }}>← Back</Link>
          <ThemeToggle tone="quiet" />
        </div>
        <div style={{ height: '.6rem' }} />
        <span className="eyebrow">Examination portal</span>
        <h1 style={{ marginTop: '.35rem' }}>Sign in to your exam</h1>
        <p className="muted small" style={{ marginTop: '.4rem', marginBottom: '1.5rem' }}>
          Use the enrolment number and exam code issued by your invigilator. The code
          works once and opens one paper.
        </p>

        <div className="panel stack" style={{ padding: '1.25rem', gap: '.9rem' }}>
          <label className="stack" style={{ gap: '.3rem' }}>
            <span className="eyebrow">Enrolment number</span>
            <input
              className="mono" value={enrollment} autoComplete="username"
              placeholder="21BCS1042"
              onChange={(e) => setEnrollment(e.target.value.toUpperCase())}
            />
          </label>
          <label className="stack" style={{ gap: '.3rem' }}>
            <span className="eyebrow">Exam code</span>
            <input
              className="mono" value={code} autoComplete="one-time-code"
              placeholder="XXXX-XXXX"
              style={{ letterSpacing: '.08em' }}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === 'Enter' && submit()}
            />
          </label>

          {error && (
            <div className="notice notice-alert">{error}</div>
          )}

          <button className="btn-primary" onClick={submit} disabled={busy}>
            {busy ? 'Checking…' : 'Begin exam'}
          </button>
        </div>

        <p className="small muted" style={{ marginTop: '1rem', lineHeight: 1.6 }}>
          Lost your code, or seeing an error? Ask your invigilator to issue a new one —
          codes cannot be recovered once issued.
        </p>
      </div>
      </div>

      <Footer bordered={false} />
    </div>
  )
}
