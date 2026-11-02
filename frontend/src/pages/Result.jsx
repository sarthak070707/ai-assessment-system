import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api.js'

export default function Result() {
  const { attemptId } = useParams()
  const [data, setData] = useState(null)
  const [answers, setAnswers] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.analytics(attemptId), api.attempt(attemptId)])
      .then(([a, b]) => { setData(a); setAnswers(b.answers) })
      .catch((e) => setError(e.message))
  }, [attemptId])

  if (error) return <p style={{ color: 'var(--alert)' }}>{error}</p>
  if (!data) return <p className="muted">Loading results…</p>

  const flagged = answers.filter((a) => a.needs_review)

  return (
    <div className="stack" style={{ gap: '2rem' }}>
      <div>
        <Link to="/" className="eyebrow" style={{ textDecoration: 'none' }}>← Assessments</Link>
        <h1 style={{ marginTop: '.4rem' }}>Result</h1>
      </div>

      <div className="panel" style={{ padding: '1.5rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '1.5rem' }}>
        {data.adaptive_paper ? (
          <>
            <Stat
              label="Estimated level" value={`${data.adaptive?.ability_percent ?? '—'}%`}
              sub="comparable across candidates" accent="var(--primary)"
            />
            <Stat
              label="Percentile" value={`${data.percentile}`}
              sub={`by level, in a cohort of ${data.cohort_size}`}
            />
            <Stat label="Marks" value={`${data.total_score}`} sub={`of ${data.max_score} served`} />
          </>
        ) : (
          <>
            <Stat label="Score" value={`${data.total_score}`} sub={`of ${data.max_score}`} />
            <Stat label="Percentage" value={`${data.percentage}%`} accent="var(--primary)" />
            <Stat label="Percentile" value={`${data.percentile}`} sub={`in a cohort of ${data.cohort_size}`} />
          </>
        )}
        <Stat
          label="Integrity flags" value={`${data.integrity_flags}`}
          accent={data.integrity_flags > 0 ? 'var(--signal)' : undefined}
        />
        <Stat
          label="Held for review" value={`${flagged.length}`}
          accent={flagged.length > 0 ? 'var(--signal)' : undefined}
        />
      </div>

      {data.adaptive && (
        <section className="panel stack" style={{ padding: '1.25rem', gap: '.75rem' }}>
          <div className="spread">
            <h2>Adaptive measurement</h2>
            <span className="tag tag-primary">adaptive paper</span>
          </div>
          <p className="small muted" style={{ margin: 0 }}>
            Questions were chosen from how you were performing, so this paper measured your level in{' '}
            {data.adaptive.questions_served} questions rather than asking everything.
          </p>
          <p className="small muted" style={{ margin: 0 }}>
            <strong style={{ color: 'var(--ink-2)' }}>Your marks are not comparable with another
            candidate's.</strong> You were served different questions worth different totals, so{' '}
            {data.percentage}% here does not mean the same as {data.percentage}% on someone else's
            paper. The estimated level does account for which questions were asked, which is why the
            ranking above uses it.
          </p>
          <div className="row" style={{ gap: '2.5rem', flexWrap: 'wrap', marginTop: '.25rem' }}>
            <div className="stack" style={{ gap: '.2rem' }}>
              <span className="eyebrow">Precision</span>
              <span className="mono" style={{ fontSize: '1.9rem', fontWeight: 600, lineHeight: 1.1 }}>
                ±{data.adaptive.precision}
              </span>
              <span className="small muted">
                {data.adaptive.stop_reason === 'precision'
                  ? 'Stopped once measured precisely enough.'
                  : 'Stopped at the question limit.'}
              </span>
            </div>
          </div>
        </section>
      )}

      {data.integrity?.total > 0 && (
        <section className="panel stack" style={{ padding: '1.25rem', gap: '.75rem', borderLeft: '3px solid var(--signal)' }}>
          <div className="spread">
            <h2>Integrity events</h2>
            <span className="mono small muted">{data.integrity.total} recorded</span>
          </div>
          <p className="small muted" style={{ margin: 0 }}>
            These are recorded, not penalised. An examiner decides what a pattern means.
          </p>

          <div className="row" style={{ gap: '.5rem', flexWrap: 'wrap' }}>
            {data.integrity.by_type.map((row) => (
              <span key={row.type} className="tag tag-signal">
                {row.label} · {row.count}
              </span>
            ))}
          </div>

          {data.integrity.unattributed.length > 0 && (
            <div className="stack" style={{ gap: '.25rem' }}>
              <span className="eyebrow">Between questions</span>
              {data.integrity.unattributed.map((e, i) => (
                <span key={i} className="small muted">
                  <span className="mono">{e.at}</span> — {e.label}
                  {e.detail && <span className="muted"> ({e.detail})</span>}
                </span>
              ))}
            </div>
          )}
        </section>
      )}

      {flagged.length > 0 && (
        <div className="panel" style={{ padding: '1rem 1.25rem', borderLeft: '3px solid var(--signal)' }}>
          <span className="eyebrow" style={{ color: 'var(--signal-tx)' }}>Provisional score</span>
          <p className="small" style={{ margin: '.35rem 0 0' }}>
            {flagged.length} {flagged.length === 1 ? 'answer' : 'answers'} scored below the confidence
            threshold and {flagged.length === 1 ? 'is' : 'are'} waiting on an examiner. Your total may change.
          </p>
        </div>
      )}

      <div className="grid-2">
        <section className="panel stack" style={{ padding: '1.25rem', gap: '1rem' }}>
          <h2>Proficiency by skill</h2>
          {data.skills.map((s) => (
            <div key={s.skill} className="stack" style={{ gap: '.35rem' }}>
              <div className="spread">
                <span className="small" style={{ fontWeight: 500 }}>{s.skill}</span>
                <span className="mono small">
                  {s.proficiency}%
                  <span className="muted" style={{ marginLeft: '.5rem' }}>{formatTime(s.seconds)}</span>
                </span>
              </div>
              <div className={`meter ${s.proficiency >= 70 ? 'is-verdict' : s.proficiency >= 40 ? 'is-signal' : 'is-alert'}`}>
                <i style={{ width: `${s.proficiency}%` }} />
              </div>
            </div>
          ))}
        </section>

        <section className="panel stack" style={{ padding: '1.25rem', gap: '.6rem' }}>
          <h2>What to work on</h2>
          {data.recommendations.map((r, i) => (
            <p key={i} className="small" style={{ margin: 0, paddingLeft: '.9rem', borderLeft: '2px solid var(--rule)' }}>
              {r}
            </p>
          ))}
        </section>
      </div>

      <section className="stack" style={{ gap: '.6rem' }}>
        <h2>Question breakdown</h2>
        <p className="small muted" style={{ margin: 0 }}>
          The confidence bar shows how certain the grader is. Anything amber went to an examiner.
        </p>
        {data.timeline.map((t, i) => {
          const answer = answers.find((a) => a.question_id === t.question_id) || {}
          const pct = t.max_score ? (100 * t.score) / t.max_score : 0
          return (
            <div key={t.question_id} className="panel" style={{ padding: '.9rem 1.1rem' }}>
              <div className="spread" style={{ gap: '1rem', alignItems: 'flex-start' }}>
                <div className="row" style={{ gap: '.75rem', flexWrap: 'wrap' }}>
                  <span className="mono muted">{String(i + 1).padStart(2, '0')}</span>
                  <span className="tag tag-primary">{t.kind}</span>
                  <span className="small muted">{t.skill} · {t.difficulty}</span>
                </div>
                <div className="row" style={{ gap: '1rem' }}>
                  {t.flags?.length > 0 && (
                    <span className="tag tag-signal">{t.flags.length} flagged</span>
                  )}
                  {t.needs_review && <span className="tag tag-signal">held for review</span>}
                  {answer.similarity_flag >= 0.85 && <span className="tag tag-alert">similarity {Math.round(answer.similarity_flag * 100)}%</span>}
                  <span className="mono small muted">{formatTime(t.seconds_spent)}</span>
                  <span className="mono" style={{ fontWeight: 600 }}>{t.score}/{t.max_score}</span>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '.7rem' }}>
                <div className="stack" style={{ gap: '.25rem' }}>
                  <span className="eyebrow">Score</span>
                  <div className={`meter ${pct >= 70 ? 'is-verdict' : pct >= 40 ? 'is-signal' : 'is-alert'}`}>
                    <i style={{ width: `${pct}%` }} />
                  </div>
                </div>
                <div className="stack" style={{ gap: '.25rem' }}>
                  <span className="eyebrow">Grader confidence</span>
                  <div className={`meter ${t.needs_review ? 'is-signal' : ''}`}>
                    <i style={{ width: `${t.confidence * 100}%` }} />
                  </div>
                </div>
              </div>

              {answer.feedback && (
                <p className="small muted" style={{ margin: '.7rem 0 0' }}>{answer.feedback}</p>
              )}

              {t.flags?.length > 0 && (
                <div className="stack" style={{
                  gap: '.25rem', marginTop: '.7rem', paddingTop: '.7rem',
                  borderTop: '1px solid var(--rule-soft)',
                }}>
                  <span className="eyebrow" style={{ color: 'var(--signal-tx)' }}>
                    {t.flags.length} integrity {t.flags.length === 1 ? 'event' : 'events'} on this question
                  </span>
                  {t.flags.map((f, fi) => (
                    <span key={fi} className="small" style={{ color: 'var(--ink-2)' }}>
                      <span className="mono muted">{f.at}</span> — {f.label}
                      {f.detail && <span className="muted"> ({f.detail})</span>}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </section>
    </div>
  )
}

function Stat({ label, value, sub, accent }) {
  return (
    <div className="stack" style={{ gap: '.2rem' }}>
      <span className="eyebrow">{label}</span>
      <span className="mono" style={{ fontSize: '1.9rem', fontWeight: 600, lineHeight: 1.1, color: accent || 'var(--ink)' }}>
        {value}
      </span>
      {sub && <span className="small muted">{sub}</span>}
    </div>
  )
}

function formatTime(seconds) {
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, '0')}s`
}
