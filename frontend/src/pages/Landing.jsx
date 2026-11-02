import { Link } from 'react-router-dom'
import ThemeToggle from '../components/ThemeToggle.jsx'
import Footer from '../components/Footer.jsx'
import DemoCredentials from '../components/DemoCredentials.jsx'

/**
 * Front door. Two ways in, no self sign-up: candidates are enrolled by the exam
 * office and hold no standing password, so there is nothing to register for.
 *
 * The staff card is distinguished by emphasis — brand-coloured border and mark —
 * rather than by inverting its surface, which would flip wrongly between themes.
 */
export default function Landing() {
  return (
    <div className="stack" style={{ minHeight: '100vh', backgroundColor: 'var(--canvas)' }}>
      <header style={{ borderBottom: '1px solid var(--rule)', background: 'var(--panel)' }}>
        <div className="spread" style={{ maxWidth: 960, margin: '0 auto', padding: '.9rem 1.5rem' }}>
          <div>
            <span style={{ fontFamily: 'var(--display)', fontWeight: 700, fontSize: '1.05rem', letterSpacing: '-.02em' }}>
              Online Assessment System
            </span>
          </div>
          <div className="row" style={{ gap: '1rem' }}>
            <span className="eyebrow">Examinations</span>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main style={{ maxWidth: 960, margin: '0 auto', padding: '4rem 1.5rem 3rem', width: '100%', flex: 1 }}>
        <div>
          <span className="eyebrow">Welcome</span>
          {/* The heading gets its own width. Sharing the paragraph's measure
              orphaned the last word onto a line by itself. */}
          <h1 style={{ marginTop: '.5rem', fontSize: '2.1rem', lineHeight: 1.15, maxWidth: 640 }}>
            Choose how you're signing in
          </h1>
          <p className="muted" style={{ marginTop: '.7rem', lineHeight: 1.65, maxWidth: 520 }}>
            Candidates sit scheduled papers using a one-time code. Staff set papers,
            issue codes and review scripts.
          </p>
        </div>

        <div className="grid-2" style={{ gap: '1rem', marginTop: '2.25rem' }}>
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
            tone="accent"
          />
        </div>

        <div style={{ marginTop: '1.25rem' }}>
          <DemoCredentials />
        </div>

        <p className="small muted" style={{ marginTop: '1.75rem', maxWidth: 520, lineHeight: 1.7 }}>
          No public registration. Candidates are enrolled by the exam office, and staff
          accounts are created for them — if you cannot sign in, that is who to ask.
        </p>
      </main>

      <Footer />
    </div>
  )
}

function Card({ to, eyebrow, title, lines, cta, tone }) {
  // 'accent' is the staff card. Distinguished by emphasis rather than by
  // inverting the surface, which would flip wrongly between themes.
  const accent = tone === 'accent'
  return (
    <Link
      to={to}
      className="panel stack portal-card"
      style={{
        padding: '1.6rem', gap: '1.25rem', textDecoration: 'none',
        justifyContent: 'space-between',
        background: accent ? 'var(--panel-2)' : 'var(--panel)',
        borderColor: accent ? 'var(--primary-br)' : 'var(--rule)',
        color: 'var(--ink)',
      }}
    >
      <div className="stack" style={{ gap: '.4rem' }}>
        <span className="portal-mark" style={{ marginBottom: '.5rem' }}>
          <Mark accent={accent} />
        </span>
        <span className="eyebrow">{eyebrow}</span>
        <h2 style={{ fontSize: '1.3rem', marginTop: '.1rem' }}>{title}</h2>
        {lines.map((line, i) => (
          <p key={i} className="small muted" style={{ margin: i ? '.15rem 0 0' : '.3rem 0 0', lineHeight: 1.6 }}>
            {line}
          </p>
        ))}
      </div>

      <span
        className="row"
        style={{ gap: '.45rem', fontWeight: 600, fontSize: '.9rem', color: 'var(--primary)' }}
      >
        {cta}
        <svg className="portal-arrow" width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path d="M3 8h9M8.5 4.5 12 8l-3.5 3.5" stroke="currentColor" strokeWidth="1.7"
            strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    </Link>
  )
}

/* Candidate: a single sheet with a clock, for a timed paper.
   Staff: stacked sheets, for a bank of papers. */
function Mark({ accent }) {
  const stroke = 'var(--primary)'
  return accent ? (
    <svg width="30" height="30" viewBox="0 0 30 30" fill="none" aria-hidden="true">
      <rect x="3.5" y="6.5" width="16" height="19" rx="2" stroke={stroke} strokeWidth="1.6" />
      <rect x="9.5" y="3.5" width="16" height="19" rx="2" stroke={stroke} strokeWidth="1.6" fill="var(--panel-2)" />
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
