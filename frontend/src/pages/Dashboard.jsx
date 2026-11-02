import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, getUser } from '../api.js'

export default function Dashboard() {
  const user = getUser()
  const isStaff = user?.role === 'controller' || user?.role === 'examiner'
  return isStaff ? <ExaminerOverview /> : <CandidateHome />
}

/** Examiners land on what needs their attention, not on a test to sit. */
function ExaminerOverview() {
  const [assessments, setAssessments] = useState([])
  const [questions, setQuestions] = useState([])
  const [queue, setQueue] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.assessments(), api.questions(), api.reviewQueue()])
      .then(([a, q, r]) => { setAssessments(a); setQuestions(q); setQueue(r) })
      .catch((e) => setError(e.message))
  }, [])

  const published = assessments.filter((a) => a.is_published).length
  const isOffice = getUser()?.role === 'controller'

  return (
    <div className="stack" style={{ gap: '1.75rem' }}>
      <div>
        <span className="eyebrow">{isOffice ? 'Exam office' : 'Your workspace'}</span>
        <h1 style={{ marginTop: '.3rem' }}>
          {isOffice ? 'All examinations' : getUser()?.full_name}
        </h1>
        {!isOffice && (
          <div className="row" style={{ gap: '.4rem', flexWrap: 'wrap', marginTop: '.5rem' }}>
            {(getUser()?.subjects || []).map((s) => (
              <span key={s} className="tag tag-primary">{s}</span>
            ))}
            {getUser()?.department && (
              <span className="tag" style={{ borderColor: 'var(--rule)', color: 'var(--ink-3)' }}>
                {getUser().department}
              </span>
            )}
          </div>
        )}
        <p className="muted small" style={{ marginTop: '.5rem' }}>
          {isOffice
            ? 'Every examiner\'s questions, papers and flagged answers.'
            : 'Only you and the exam office can see anything here. No other examiner can.'}
        </p>
      </div>

      {error && <p style={{ color: 'var(--alert)' }}>{error}</p>}

      <div className="panel" style={{ padding: '1.5rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1.5rem' }}>
        <Stat label={isOffice ? 'All questions' : 'Your questions'} value={questions.length} to="/questions" />
        <Stat label={isOffice ? 'All assessments' : 'Your assessments'} value={assessments.length} sub={`${published} published`} to="/assessments" />
        <Stat label="Awaiting review" value={queue.length} to="/review" accent={queue.length ? 'var(--signal)' : undefined} />
      </div>

      {queue.length > 0 && (
        <div className="panel" style={{ padding: '1rem 1.25rem', borderLeft: '3px solid var(--signal)' }}>
          <span className="eyebrow" style={{ color: 'var(--signal-tx)' }}>Needs a decision</span>
          <p className="small" style={{ margin: '.35rem 0 .6rem' }}>
            {queue.length} answer{queue.length === 1 ? '' : 's'} the grader was not confident enough to score.
            Candidates see these totals as provisional until you confirm them.
          </p>
          <Link to="/review" className="small" style={{ color: 'var(--primary)' }}>Open review queue →</Link>
        </div>
      )}

      <div className="stack" style={{ gap: '.6rem' }}>
        <h2>{isOffice ? 'All assessments' : 'Your assessments'}</h2>
        {assessments.map((a) => (
          <Link key={a.id} to="/assessments" className="panel spread" style={{ padding: '.9rem 1.25rem', textDecoration: 'none', color: 'inherit' }}>
            <span style={{ fontWeight: 500 }}>{a.title}</span>
            <div className="row" style={{ gap: '.75rem' }}>
              <span className="mono small muted">{a.question_ids.length} questions</span>
              <span className={`tag ${a.is_published ? 'tag-verdict' : 'tag-signal'}`}>
                {a.is_published ? 'published' : 'draft'}
              </span>
            </div>
          </Link>
        ))}
        {!assessments.length && (
          <div className="panel" style={{ padding: '2rem', textAlign: 'center' }}>
            <p className="muted" style={{ margin: 0 }}>No assessments yet. Build one from your question bank.</p>
          </div>
        )}
      </div>
    </div>
  )
}

function Stat({ label, value, sub, to, accent }) {
  return (
    <Link to={to} className="stack" style={{ gap: '.2rem', textDecoration: 'none', color: 'inherit' }}>
      <span className="eyebrow">{label}</span>
      <span className="mono" style={{ fontSize: '1.9rem', fontWeight: 600, lineHeight: 1.1, color: accent || 'var(--ink)' }}>
        {value}
      </span>
      {sub && <span className="small muted">{sub}</span>}
    </Link>
  )
}

function CandidateHome() {
  const [assessments, setAssessments] = useState([])
  const [attempts, setAttempts] = useState([])
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const user = getUser()

  useEffect(() => {
    Promise.all([api.assessments(), api.myAttempts()])
      .then(([a, b]) => { setAssessments(a); setAttempts(b) })
      .catch((e) => setError(e.message))
  }, [])

  const submitted = attempts.filter((a) => a.status === 'submitted')

  return (
    <div className="stack" style={{ gap: '2rem' }}>
      <div>
        <span className="eyebrow">Candidate</span>
        <h1 style={{ marginTop: '.3rem' }}>
          {assessments.length === 1 ? 'Your exam' : 'Available assessments'}
        </h1>
        <p className="muted small" style={{ marginTop: '.4rem' }}>
          Your exam code opens this paper, once. Sitting another requires its own code.
        </p>
      </div>

      {error && <p style={{ color: 'var(--alert)' }}>{error}</p>}

      <div className="stack" style={{ gap: '.75rem' }}>
        {assessments.map((a) => (
          <div key={a.id} className="panel spread" style={{
            padding: '1.1rem 1.25rem', gap: '1rem',
            opacity: a.opens_with_your_code ? 1 : 0.55,
          }}>
            <div>
              <div className="row" style={{ gap: '.5rem', flexWrap: 'wrap' }}>
                <h2>{a.title}</h2>
                {a.mode === 'adaptive' && <span className="tag tag-primary">adaptive</span>}
              </div>
              <p className="small muted" style={{ margin: '.3rem 0 .5rem' }}>{a.description}</p>
              <span className="mono small muted">
                {a.question_ids.length} questions · {a.duration_minutes} min
              </span>
            </div>
            {/* The server decides all three states: only it knows which code
                opened this session. The page just renders the verdict. */}
            {!a.opens_with_your_code ? (
              <div className="stack" style={{ alignItems: 'flex-end', gap: '.3rem' }}>
                <span className="tag" style={{ borderColor: 'var(--rule)', color: 'var(--ink-3)' }}>
                  not this sitting
                </span>
                <span className="small muted" style={{ maxWidth: 220, textAlign: 'right' }}>
                  Your code opens a different paper.
                </span>
              </div>
            ) : a.sitting_used ? (
              <div className="stack" style={{ alignItems: 'flex-end', gap: '.3rem' }}>
                <span className="tag tag-verdict">submitted</span>
                <span className="small muted" style={{ maxWidth: 220, textAlign: 'right' }}>
                  Ask your invigilator for a new code if you need to sit it again.
                </span>
              </div>
            ) : (
              <button className="btn-primary" onClick={() => navigate(`/test/${a.id}`)}>
                {a.in_progress ? 'Resume assessment' : 'Start assessment'}
              </button>
            )}
          </div>
        ))}
        {!assessments.length && !error && (
          <div className="panel" style={{ padding: '2rem', textAlign: 'center' }}>
            <p style={{ margin: 0, fontWeight: 500 }}>Nothing to sit right now</p>
            <p className="muted small" style={{ margin: '.35rem 0 0' }}>
              Your code does not open a published paper. Ask your invigilator.
            </p>
          </div>
        )}
      </div>

      {submitted.length > 0 && (
        <div className="stack" style={{ gap: '.75rem' }}>
          <h2>Your results</h2>
          {submitted.map((a) => {
            const pct = a.max_score ? Math.round((100 * a.total_score) / a.max_score) : 0
            return (
              <Link
                key={a.id} to={`/result/${a.id}`}
                className="panel spread"
                style={{ padding: '.9rem 1.25rem', textDecoration: 'none', color: 'inherit' }}
              >
                <div>
                  <span className="mono" style={{ fontWeight: 600 }}>{a.total_score} / {a.max_score}</span>
                  <span className="small muted" style={{ marginLeft: '.75rem' }}>
                    submitted {new Date(a.submitted_at).toLocaleDateString()}
                  </span>
                </div>
                <div className="row" style={{ gap: '1rem' }}>
                  {a.integrity_flags > 0 && (
                    <span className="tag tag-signal">{a.integrity_flags} integrity flags</span>
                  )}
                  <span className="mono" style={{ fontWeight: 600, color: 'var(--primary)' }}>{pct}%</span>
                </div>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
