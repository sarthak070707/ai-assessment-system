import { useEffect, useState } from 'react'
import { api, getUser } from '../api.js'

/**
 * The examiner's queue. Only answers the grader was unsure about land here, so
 * the human spends attention where the model was weakest rather than re-marking
 * everything.
 */
export default function Review() {
  const [rows, setRows] = useState([])
  const [drafts, setDrafts] = useState({})
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(null)

  const load = () => api.reviewQueue().then(setRows).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  async function confirm(row, score) {
    setSaving(row.answer_id)
    try {
      await api.applyReview(row.answer_id, score, drafts[row.answer_id]?.feedback || '')
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(null)
    }
  }

  return (
    <div className="stack" style={{ gap: '1.5rem' }}>
      <div>
        <span className="eyebrow">
          {getUser()?.role === 'controller' ? 'Exam office' : 'Your papers'}
        </span>
        <h1 style={{ marginTop: '.3rem' }}>Review queue</h1>
        <p className="muted small" style={{ marginTop: '.4rem' }}>
          Answers the grader scored with low confidence, or that closely match another submission.
          {getUser()?.role !== 'controller' && ' Only scripts from your own assessments appear here.'}
        </p>
      </div>

      {error && <p style={{ color: 'var(--alert)' }}>{error}</p>}

      {!rows.length && !error && (
        <div className="panel" style={{ padding: '2.5rem', textAlign: 'center' }}>
          <p style={{ margin: 0, fontWeight: 500 }}>Nothing waiting</p>
          <p className="muted small" style={{ margin: '.35rem 0 0' }}>
            Every answer graded so far cleared the confidence threshold.
          </p>
        </div>
      )}

      {rows.map((row) => {
        const draft = drafts[row.answer_id] || {}
        const score = draft.score ?? row.ai_score
        return (
          <div key={row.answer_id} className="panel stack" style={{ padding: '1.25rem', gap: '.9rem' }}>
            <div className="spread" style={{ gap: '1rem', alignItems: 'flex-start' }}>
              <p style={{ margin: 0, fontWeight: 500 }}>{row.prompt}</p>
              <div className="row" style={{ gap: '.5rem', flexShrink: 0 }}>
                <span className="tag tag-signal">confidence {row.confidence}</span>
                {row.similarity_flag >= 0.85 && (
                  <span className="tag tag-alert">similarity {Math.round(row.similarity_flag * 100)}%</span>
                )}
              </div>
            </div>

            <div style={{
              background: 'var(--canvas)', border: '1px solid var(--rule-soft)',
              borderRadius: 'var(--r)', padding: '.8rem', whiteSpace: 'pre-wrap',
              fontFamily: 'var(--mono)', fontSize: '.82rem', lineHeight: 1.6,
            }}>
              {row.response_text || '(no answer submitted)'}
            </div>

            <p className="small muted" style={{ margin: 0 }}>
              Grader suggested <span className="mono">{row.ai_score}</span> of{' '}
              <span className="mono">{row.max_score}</span>. {row.feedback}
            </p>

            <div className="row" style={{ gap: '.75rem', flexWrap: 'wrap' }}>
              <label className="stack" style={{ gap: '.25rem', width: 110 }}>
                <span className="eyebrow">Final score</span>
                <input
                  type="number" className="mono" min="0" max={row.max_score} step="0.5" value={score}
                  onChange={(e) => setDrafts((d) => ({
                    ...d, [row.answer_id]: { ...d[row.answer_id], score: Number(e.target.value) },
                  }))}
                />
              </label>
              <label className="stack" style={{ gap: '.25rem', flex: 1, minWidth: 220 }}>
                <span className="eyebrow">Note to candidate</span>
                <input
                  placeholder="Optional"
                  value={draft.feedback ?? ''}
                  onChange={(e) => setDrafts((d) => ({
                    ...d, [row.answer_id]: { ...d[row.answer_id], feedback: e.target.value },
                  }))}
                />
              </label>
              <button
                className="btn-primary"
                style={{ alignSelf: 'flex-end' }}
                disabled={saving === row.answer_id}
                onClick={() => confirm(row, score)}
              >
                {saving === row.answer_id ? 'Saving…' : 'Confirm score'}
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
