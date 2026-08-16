import { Link } from 'react-router-dom'

/**
 * Front door. Two ways in, no self sign-up: candidates are enrolled by the exam
 * office and hold no standing password, so there is nothing to register for.
 *
 * Each card is styled like the portal behind it — candidate light, staff dark —
 * so the split between the two is visible before you commit to either.
 */
export default function Landing() {
  return (
    <div className="stack" style={{ minHeight: '100vh', background: 'var(--canvas)' }}>
      <header style={{ borderBottom: '1px solid var(--rule)', background: 'var(--panel)' }}>
        <div className="spread" style={{ maxWidth: 1020, margin: '0 auto', padding: '1.1rem 1.5rem' }}>
          <div>
            <span style={{ fontFamily: 'var(--display)', fontWeight: 700, fontSize: '1.05rem', letterSpacing: '-.02em' }}>
              Online Assessment System
            </span>
            <span className="mono muted" style={{ marginLeft: 10, fontSize: '.7rem' }}>v1.0</span>
          </div>
          <span className="eyebrow">Examinations</span>
        </div>
      </header>

      <main style={{ maxWidth: 1020, margin: '0 auto', padding: '3.5rem 1.5rem 4rem', width: '100%' }}>
        <div style={{ maxWidth: 560 }}>
          <span className="eyebrow">Welcome</span>
          <h1 style={{ marginTop: '.4rem', fontSize: '2rem' }}>Choose how you're signing in</h1>
          <p className="muted" style={{ marginTop: '.6rem', lineHeight: 1.65 }}>
            Candidates sit scheduled papers using a one-time code. Staff set papers,
            issue codes and review scripts.
          </p>
        </div>

        <div className="grid-2" style={{ gap: '1.25rem', marginTop: '2.5rem' }}>
          <Card
            to="/login"
            eyebrow="Candidates"
            title="Sit an exam"
            lines={[
              'Sign in with your enrolment number and the exam code your invigilator gives you.',
              'The code opens one paper and works once.',
            ]}
            cta="Enter examination"
            tone="light"
          />
          <Card
            to="/admin"
            eyebrow="Faculty and exam office"
            title="Staff sign in"
            lines={[
              'Sign in with your staff ID or institutional email.',
              'Question bank, paper scheduling, exam codes and score review.',
            ]}
            cta="Staff portal"
            tone="dark"
          />
        </div>

        <p className="small muted" style={{ marginTop: '2.5rem', maxWidth: 560, lineHeight: 1.7 }}>
          No public registration. Candidates are enrolled by the exam office, and staff
          accounts are created for them — if you cannot sign in, that is who to ask.
        </p>
      </main>
    </div>
  )
}

function Card({ to, eyebrow, title, lines, cta, tone }) {
  const dark = tone === 'dark'
  return (
    <Link
      to={to}
      className="panel stack"
      style={{
        padding: '1.75rem', gap: '.6rem', textDecoration: 'none',
        justifyContent: 'space-between', minHeight: 260,
        background: dark ? 'var(--ink)' : 'var(--panel)',
        borderColor: dark ? 'var(--ink)' : 'var(--rule)',
        color: dark ? '#fff' : 'var(--ink)',
      }}
    >
      <div className="stack" style={{ gap: '.5rem' }}>
        <Mark dark={dark} />
        <span className="eyebrow" style={{ color: dark ? '#8C96A5' : 'var(--ink-3)', marginTop: '.5rem' }}>
          {eyebrow}
        </span>
        <h2 style={{ fontSize: '1.35rem' }}>{title}</h2>
        {lines.map((line, i) => (
          <p key={i} className="small" style={{ margin: 0, color: dark ? '#8C96A5' : 'var(--ink-3)', lineHeight: 1.6 }}>
            {line}
          </p>
        ))}
      </div>

      <span
        className="row"
        style={{
          gap: '.5rem', marginTop: '1rem', fontWeight: 600, fontSize: '.9rem',
          color: dark ? '#fff' : 'var(--primary)',
        }}
      >
        {cta}
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path d="M3 8h9M8.5 4.5 12 8l-3.5 3.5" stroke="currentColor" strokeWidth="1.6"
            strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    </Link>
  )
}

/* Candidate: a single sheet with a clock, for a timed paper.
   Staff: stacked sheets, for a bank of papers. */
function Mark({ dark }) {
  const stroke = dark ? '#8C96A5' : 'var(--primary)'
  return dark ? (
    <svg width="30" height="30" viewBox="0 0 30 30" fill="none" aria-hidden="true">
      <rect x="3.5" y="6.5" width="16" height="19" rx="2" stroke={stroke} strokeWidth="1.6" />
      <rect x="9.5" y="3.5" width="16" height="19" rx="2" stroke={stroke} strokeWidth="1.6" fill={dark ? 'var(--ink)' : 'var(--panel)'} />
      <path d="M13 9h9M13 12.5h9M13 16h5" stroke={stroke} strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ) : (
    <svg width="30" height="30" viewBox="0 0 30 30" fill="none" aria-hidden="true">
      <rect x="4.5" y="3.5" width="16" height="23" rx="2" stroke={stroke} strokeWidth="1.6" />
      <path d="M8.5 9h8M8.5 13h8M8.5 17h4" stroke={stroke} strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="22" cy="21" r="5.2" fill="var(--panel)" stroke={stroke} strokeWidth="1.6" />
      <path d="M22 18.6V21l1.7 1.1" stroke={stroke} strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}
