import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api.js'
import Timer from '../components/Timer.jsx'
import useProctor from '../components/useProctor.js'

export default function TakeTest() {
  const { assessmentId } = useParams()
  const navigate = useNavigate()

  const [session, setSession] = useState(null)
  const [index, setIndex] = useState(0)
  const [answers, setAnswers] = useState({})
  const [flags, setFlags] = useState(0)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [savedAt, setSavedAt] = useState(null)
  const [saving, setSaving] = useState(false)

  // Time per question is measured, not asked for: it feeds the analytics report.
  const enteredAt = useRef(Date.now())
  const spent = useRef({})

  useEffect(() => {
    api.startAttempt(assessmentId)
      .then((data) => {
        setSession(data)
        // Restore saved work. Time spent is restored too, so resuming does not
        // reset the per-question timings the analytics report is built from.
        const restored = {}
        for (const a of data.draft_answers || []) {
          restored[a.question_id] = {
            response_text: a.response_text || '',
            selected_option: a.selected_option ?? null,
          }
          if (a.seconds_spent) spent.current[a.question_id] = a.seconds_spent
        }
        if (Object.keys(restored).length) {
          setAnswers(restored)
          setSavedAt(data.draft_saved_at ? new Date(data.draft_saved_at) : null)
        }
      })
      .catch((e) => setError(e.message))
  }, [assessmentId])

  const questions = session?.questions ?? []
  const question = questions[index]

  // Declared after `question`: hooks run in order, and reading it above would
  // hit the temporal dead zone on a const declared further down.
  useProctor(session?.attempt?.id, {
    onFlag: () => setFlags((n) => n + 1),
    questionId: question?.id,
  })

  // Snapshot of everything worth saving, rebuilt whenever an answer changes.
  const draft = useMemo(
    () => questions.map((q) => ({
      question_id: q.id,
      response_text: answers[q.id]?.response_text ?? '',
      selected_option: answers[q.id]?.selected_option ?? null,
      seconds_spent: spent.current[q.id] || 0,
    })),
    [answers, questions]
  )

  // Saved two seconds after typing stops, and again every half minute while the
  // paper is open. Debouncing alone would never fire for a candidate who types
  // continuously; an interval alone would lose up to thirty seconds of work.
  useEffect(() => {
    const id = session?.attempt?.id
    if (!id || submitting || !questions.length) return

    let cancelled = false
    const push = async () => {
      if (cancelled) return
      setSaving(true)
      try {
        const result = await api.saveDraft(id, draft)
        if (!cancelled) setSavedAt(new Date(result.saved_at))
      } catch {
        // Silent: a failed autosave must not interrupt someone sitting an exam.
        // The next attempt is thirty seconds away and carries the same content.
      } finally {
        if (!cancelled) setSaving(false)
      }
    }

    const debounce = setTimeout(push, 2000)
    const heartbeat = setInterval(push, 30000)
    return () => { cancelled = true; clearTimeout(debounce); clearInterval(heartbeat) }
  }, [draft, session, submitting, questions.length])

  const recordTime = useCallback(() => {
    if (!question) return
    const elapsed = Math.round((Date.now() - enteredAt.current) / 1000)
    spent.current[question.id] = (spent.current[question.id] || 0) + elapsed
    enteredAt.current = Date.now()
  }, [question])

  function goTo(next) {
    recordTime()
    setIndex(next)
  }

  function setAnswer(patch) {
    setAnswers((prev) => ({ ...prev, [question.id]: { ...prev[question.id], ...patch } }))
  }

  const submit = useCallback(async () => {
    if (submitting || !session) return
    setSubmitting(true)
    recordTime()
    const payload = questions.map((q) => ({
      question_id: q.id,
      response_text: answers[q.id]?.response_text ?? '',
      selected_option: answers[q.id]?.selected_option ?? null,
      seconds_spent: spent.current[q.id] || 0,
    }))
    try {
      const result = await api.submitAttempt(session.attempt.id, payload)
      navigate(`/result/${result.id}`, { replace: true })
    } catch (e) {
      setError(e.message)
      setSubmitting(false)
    }
  }, [answers, navigate, questions, recordTime, session, submitting])

  if (error) {
    return (
      <div style={{ maxWidth: 520, margin: '4rem auto', padding: '0 1.5rem' }}>
        <h1>{error.includes('already submitted') ? 'Already submitted' : "Can't load this assessment"}</h1>
        <p className="muted" style={{ marginTop: '.5rem' }}>{error}</p>
        <button className="btn-ghost" style={{ marginTop: '1rem' }} onClick={() => navigate('/')}>
          Back to assessments
        </button>
      </div>
    )
  }
  if (!session) return <p style={{ padding: '3rem', textAlign: 'center' }} className="muted">Loading assessment…</p>

  const answered = questions.filter((q) => {
    const a = answers[q.id]
    return a && (a.selected_option != null || (a.response_text || '').trim())
  }).length

  return (
    <div>
      <header style={{
        background: 'var(--panel)', borderBottom: '1px solid var(--rule)',
        padding: '1rem 1.5rem', position: 'sticky', top: 3, zIndex: 20,
      }}>
        <div className="spread" style={{ maxWidth: 1120, margin: '0 auto' }}>
          <div>
            <span className="eyebrow">In progress</span>
            <h2 style={{ marginTop: '.15rem' }}>{session.assessment.title}</h2>
          </div>
          <div className="row" style={{ gap: '1.75rem' }}>
            {flags > 0 && <span className="tag tag-signal">{flags} integrity {flags === 1 ? 'flag' : 'flags'}</span>}
            <div className="stack" style={{ alignItems: 'flex-end' }}>
              <span className="eyebrow">Answered</span>
              <span className="mono" style={{ fontSize: '1.45rem', fontWeight: 600, lineHeight: 1.1 }}>
                {answered}/{questions.length}
              </span>
            </div>
            {/* Remaining time comes from the server, computed from when the
                attempt began. Deriving it here from the duration meant a reload
                handed the candidate a fresh clock. */}
            <Timer
              totalSeconds={session.assessment.duration_minutes * 60}
              secondsRemaining={session.assessment.seconds_remaining}
              onExpire={submit}
            />
          </div>
        </div>
      </header>

      <div style={{
        maxWidth: 1120, margin: '0 auto', padding: '1.75rem 1.5rem 4rem',
        display: 'grid', gridTemplateColumns: '180px 1fr', gap: '1.75rem', alignItems: 'start',
      }}>
        <nav className="panel stack" style={{ padding: '1rem', gap: '.75rem', position: 'sticky', top: 100 }}>
          <span className="eyebrow">Questions</span>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '.4rem' }}>
            {questions.map((q, i) => {
              const a = answers[q.id]
              const done = a && (a.selected_option != null || (a.response_text || '').trim())
              const active = i === index
              return (
                <button
                  key={q.id}
                  onClick={() => goTo(i)}
                  aria-current={active ? 'step' : undefined}
                  aria-label={`Question ${i + 1}${done ? ', answered' : ', not answered'}`}
                  className="mono"
                  style={{
                    padding: '.4rem 0', fontSize: '.8rem', fontWeight: 600,
                    border: `1px solid ${active ? 'var(--primary)' : 'var(--rule)'}`,
                    background: active ? 'var(--primary)' : done ? 'var(--verdict-10)' : 'transparent',
                    color: active ? '#fff' : done ? 'var(--verdict)' : 'var(--ink-3)',
                  }}
                >
                  {i + 1}
                </button>
              )
            })}
          </div>
          <button className="btn-primary" onClick={submit} disabled={submitting} style={{ marginTop: '.25rem' }}>
            {submitting ? 'Grading…' : 'Submit assessment'}
          </button>
          <p className="small muted" style={{ margin: 0 }}>
            You can revisit any question until you submit.
          </p>
          <div className="stack" style={{ gap: '.15rem', borderTop: '1px solid var(--rule-soft)', paddingTop: '.6rem' }}>
            <span className="eyebrow">Your work</span>
            <span className="small" style={{ color: savedAt ? 'var(--verdict)' : 'var(--ink-3)' }}>
              {saving ? 'Saving…'
                : savedAt ? `Saved ${savedAt.toLocaleTimeString()}`
                : 'Not saved yet'}
            </span>
          </div>
        </nav>

        <section className="panel stack" style={{ padding: '1.5rem', gap: '1.1rem' }}>
          <div className="row" style={{ gap: '.5rem', flexWrap: 'wrap' }}>
            <span className="tag tag-primary">{question.kind}</span>
            <span className="tag" style={{ borderColor: 'var(--rule)', color: 'var(--ink-3)' }}>{question.skill}</span>
            <span className="tag" style={{ borderColor: 'var(--rule)', color: 'var(--ink-3)' }}>{question.difficulty}</span>
            <span className="mono small muted" style={{ marginLeft: 'auto' }}>{question.max_score} marks</span>
          </div>

          <p style={{ margin: 0, fontSize: '1rem', lineHeight: 1.65 }}>
            <span className="mono muted" style={{ marginRight: '.6rem' }}>
              {String(index + 1).padStart(2, '0')}
            </span>
            {question.prompt}
          </p>

          {question.kind === 'mcq' && (
            <div className="stack" style={{ gap: '.5rem' }}>
              {question.options.map((opt, i) => {
                const selected = answers[question.id]?.selected_option === i
                return (
                  <label key={i} className="row" style={{
                    gap: '.65rem', padding: '.65rem .8rem', cursor: 'pointer',
                    border: `1px solid ${selected ? 'var(--primary)' : 'var(--rule)'}`,
                    background: selected ? 'var(--primary-10)' : 'transparent',
                    borderRadius: 'var(--r)',
                  }}>
                    <input
                      type="radio" name={`q${question.id}`} checked={selected}
                      onChange={() => setAnswer({ selected_option: i })}
                      style={{ width: 'auto', margin: 0 }}
                    />
                    <span className="mono small muted">{String.fromCharCode(65 + i)}</span>
                    <span>{opt}</span>
                  </label>
                )
              })}
            </div>
          )}

          {question.kind === 'coding' && (
            <textarea
              className="code" rows={16} data-answer="1" spellCheck="false"
              value={answers[question.id]?.response_text ?? question.starter_code ?? ''}
              onChange={(e) => setAnswer({ response_text: e.target.value })}
            />
          )}

          {question.kind === 'descriptive' && (
            <textarea
              rows={9} data-answer="1"
              placeholder="Write your answer. It is graded on meaning, not exact wording."
              value={answers[question.id]?.response_text ?? ''}
              onChange={(e) => setAnswer({ response_text: e.target.value })}
            />
          )}

          <div className="spread" style={{ borderTop: '1px solid var(--rule-soft)', paddingTop: '1rem' }}>
            <button className="btn-ghost" disabled={index === 0} onClick={() => goTo(index - 1)}>
              Previous
            </button>
            <button
              className="btn-ghost"
              disabled={index === questions.length - 1}
              onClick={() => goTo(index + 1)}
            >
              Next
            </button>
          </div>
        </section>
      </div>
    </div>
  )
}
