import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api.js'
import Timer from '../components/Timer.jsx'
import useProctor from '../components/useProctor.js'

/**
 * An adaptive paper: one question at a time, chosen from how the candidate is
 * doing so far.
 *
 * Deliberately no question navigator and no going back. In a fixed paper
 * revisiting an answer is harmless; here an earlier answer has already decided
 * what came after it, so changing it would invalidate the sequence. Saying so
 * up front is fairer than letting someone discover it by trying.
 *
 * No progress bar of ability either. Showing a candidate their running estimate
 * mid-examination tells them whether the next question will be harder, which
 * changes how they answer it.
 */
export default function AdaptiveTest() {
  const { assessmentId } = useParams()
  const navigate = useNavigate()

  const [session, setSession] = useState(null)
  const [question, setQuestion] = useState(null)
  const [answered, setAnswered] = useState(0)
  const [draft, setDraft] = useState({ response_text: '', selected_option: null })
  const [flags, setFlags] = useState(0)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const enteredAt = useRef(Date.now())

  useEffect(() => {
    api.startAttempt(assessmentId)
      .then((data) => {
        setSession(data)
        setQuestion(data.questions?.[0] ?? null)
        setAnswered(data.answered ?? 0)
        enteredAt.current = Date.now()
      })
      .catch((e) => setError(e.message))
  }, [assessmentId])

  useProctor(session?.attempt?.id, {
    onFlag: () => setFlags((n) => n + 1),
    questionId: question?.id,
  })

  const submitAnswer = useCallback(async () => {
    if (!question || busy || !session) return
    setBusy(true)
    try {
      const step = await api.adaptiveAnswer(session.attempt.id, {
        question_id: question.id,
        response_text: draft.response_text ?? '',
        selected_option: draft.selected_option ?? null,
        seconds_spent: Math.round((Date.now() - enteredAt.current) / 1000),
      })
      if (step.finished) {
        navigate(`/result/${step.attempt_id}`, { replace: true })
        return
      }
      setQuestion(step.question)
      setAnswered(step.answered)
      setDraft({ response_text: '', selected_option: null })
      enteredAt.current = Date.now()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }, [busy, draft, navigate, question, session])

  const expire = useCallback(() => { submitAnswer() }, [submitAnswer])

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
  if (!question) return <p style={{ padding: '3rem', textAlign: 'center' }} className="muted">Finishing up…</p>

  const total = session.assessment.max_questions
  const hasAnswer = draft.selected_option !== null || (draft.response_text || '').trim().length > 0

  return (
    <div>
      <header style={{
        background: 'var(--panel)', borderBottom: '1px solid var(--rule)',
        padding: '1rem 1.5rem', position: 'sticky', top: 3, zIndex: 20,
      }}>
        <div className="spread" style={{ maxWidth: 880, margin: '0 auto' }}>
          <div>
            <span className="eyebrow">Adaptive · in progress</span>
            <h2 style={{ marginTop: '.15rem' }}>{session.assessment.title}</h2>
          </div>
          <div className="row" style={{ gap: '1.75rem' }}>
            {flags > 0 && <span className="tag tag-signal">{flags} integrity {flags === 1 ? 'flag' : 'flags'}</span>}
            <div className="stack" style={{ alignItems: 'flex-end' }}>
              <span className="eyebrow">Question</span>
              <span className="mono" style={{ fontSize: '1.45rem', fontWeight: 600, lineHeight: 1.1 }}>
                {answered + 1}<span className="muted" style={{ fontSize: '.9rem' }}> of up to {total}</span>
              </span>
            </div>
            <Timer
              totalSeconds={session.assessment.duration_minutes * 60}
              secondsRemaining={session.assessment.seconds_remaining}
              onExpire={expire}
            />
          </div>
        </div>
      </header>

      <div style={{ maxWidth: 880, margin: '0 auto', padding: '1.75rem 1.5rem 4rem' }}>
        <div className="panel" style={{ padding: '.85rem 1.1rem', marginBottom: '1rem', borderLeft: '3px solid var(--primary)' }}>
          <p className="small" style={{ margin: 0 }}>
            Questions are chosen from how you are doing, so you cannot return to an earlier one.
            The paper ends once it has measured enough, or after {total} questions.
          </p>
        </div>

        <section className="panel stack" style={{ padding: '1.5rem', gap: '1.1rem' }}>
          <div className="row" style={{ gap: '.5rem', flexWrap: 'wrap' }}>
            <span className="tag tag-primary">{question.kind}</span>
            <span className="tag">{question.skill}</span>
            <span className="tag">{question.difficulty}</span>
            <span className="mono small muted" style={{ marginLeft: 'auto' }}>{question.max_score} marks</span>
          </div>

          <p style={{ margin: 0, fontSize: '1rem', lineHeight: 1.65 }}>{question.prompt}</p>

          {question.kind === 'mcq' && (
            <div className="stack" style={{ gap: '.5rem' }}>
              {question.options.map((opt, i) => {
                const selected = draft.selected_option === i
                return (
                  <label key={i} className="row" style={{
                    gap: '.65rem', padding: '.65rem .8rem', cursor: 'pointer',
                    border: `1px solid ${selected ? 'var(--primary)' : 'var(--rule)'}`,
                    background: selected ? 'var(--primary-10)' : 'transparent',
                    borderRadius: 'var(--r)',
                  }}>
                    <input type="radio" name={`q${question.id}`} checked={selected}
                      onChange={() => setDraft((d) => ({ ...d, selected_option: i }))}
                      style={{ width: 'auto', margin: 0 }} />
                    <span className="mono small muted">{String.fromCharCode(65 + i)}</span>
                    <span>{opt}</span>
                  </label>
                )
              })}
            </div>
          )}

          {question.kind === 'coding' && (
            <textarea className="code" rows={16} data-answer="1" spellCheck="false"
              value={draft.response_text || question.starter_code || ''}
              onChange={(e) => setDraft((d) => ({ ...d, response_text: e.target.value }))} />
          )}

          {question.kind === 'descriptive' && (
            <textarea rows={9} data-answer="1"
              placeholder="Write your answer. It is graded on meaning, not exact wording."
              value={draft.response_text}
              onChange={(e) => setDraft((d) => ({ ...d, response_text: e.target.value }))} />
          )}

          <div className="spread" style={{ borderTop: '1px solid var(--rule-soft)', paddingTop: '1rem' }}>
            <span className="small muted">
              {hasAnswer ? 'Answering moves you on for good.' : 'You can submit without answering, but it will score zero.'}
            </span>
            <button className="btn-primary" onClick={submitAnswer} disabled={busy}>
              {busy ? 'Grading…' : answered + 1 >= total ? 'Submit and finish' : 'Submit and continue'}
            </button>
          </div>
        </section>
      </div>
    </div>
  )
}
