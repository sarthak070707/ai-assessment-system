import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, getUser } from '../api.js'

/**
 * Bulk import from a question paper.
 *
 * Two stages, deliberately: the parser proposes, the examiner decides. Reading
 * questions out of a human-formatted document is guesswork, and a mis-read
 * answer key would mark correct work wrong without anyone noticing. So nothing
 * reaches the bank until every question has been looked at.
 */
export default function ImportQuestions() {
  const me = getUser()
  const mySubjects = me?.subjects || []
  const isOffice = me?.role === 'controller'

  const [text, setText] = useState('')
  const [defaultMarks, setDefaultMarks] = useState(5)
  const [subject, setSubject] = useState(mySubjects[0] || '')
  const [drafts, setDrafts] = useState(null)
  const [meta, setMeta] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const fileInput = useRef(null)
  const navigate = useNavigate()

  async function preview(fn) {
    setError(''); setBusy(true)
    try {
      const result = await fn()
      setMeta({ backend: result.backend, note: result.note })
      setDrafts(result.questions.map((q) => ({ ...q, include: q.warnings.length === 0 })))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const setDraft = (i, patch) =>
    setDrafts((d) => d.map((row, j) => (j === i ? { ...row, ...patch } : row)))

  async function save() {
    setError('')
    const chosen = drafts.filter((d) => d.include)
    if (!chosen.length) return setError('Tick at least one question to save.')
    if (!subject) return setError('Choose the subject these questions belong to.')

    const unresolved = chosen.filter(
      (d) => (d.kind === 'mcq' && d.correct_option === null) ||
             (d.kind === 'descriptive' && !d.reference_answer.trim()) ||
             (d.kind === 'coding')
    )
    if (unresolved.length) {
      return setError(
        `${unresolved.length} selected question${unresolved.length === 1 ? '' : 's'} still ` +
        'need work. Coding questions need test cases, which must be added individually — ' +
        'untick those and add them from the question bank.'
      )
    }

    setBusy(true)
    try {
      const payload = chosen.map((d) => ({
        kind: d.kind,
        skill: subject,
        difficulty: d.difficulty,
        prompt: d.prompt,
        max_score: Number(d.max_score),
        options: d.kind === 'mcq' ? d.options : null,
        correct_option: d.kind === 'mcq' ? d.correct_option : null,
        reference_answer: d.kind === 'descriptive' ? d.reference_answer : null,
        rubric_keywords: d.kind === 'descriptive' ? d.rubric_keywords : null,
      }))
      await api.importCommit(subject, payload)
      navigate('/questions')
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }

  if (drafts) {
    const selected = drafts.filter((d) => d.include).length
    const flagged = drafts.filter((d) => d.warnings.length).length
    return (
      <div className="stack" style={{ gap: '1.25rem' }}>
        <div>
          <button className="eyebrow" style={{ background: 'none', border: 'none', padding: 0 }}
            onClick={() => { setDrafts(null); setError('') }}>
            ← Start over
          </button>
          <h1 style={{ marginTop: '.4rem' }}>Review before saving</h1>
          <p className="muted small" style={{ marginTop: '.4rem' }}>
            {drafts.length} question{drafts.length === 1 ? '' : 's'} read
            {flagged > 0 && <>, <span style={{ color: 'var(--signal)' }}>{flagged} needing attention</span></>}.
            Nothing is saved until you press the button at the bottom.
          </p>
          {meta && (
            <div className="row" style={{ gap: '.5rem', marginTop: '.6rem', flexWrap: 'wrap' }}>
              <span className={`tag ${meta.backend === 'groq' ? 'tag-primary' : ''}`}
                style={meta.backend !== 'groq' ? { borderColor: 'var(--rule)', color: 'var(--ink-3)' } : {}}>
                {meta.backend === 'groq' ? 'read by AI' : 'pattern matching'}
              </span>
              <span className="small muted">{meta.note}</span>
            </div>
          )}
        </div>

        {error && <Banner tone="alert">{error}</Banner>}

        <section className="panel row" style={{ padding: '1rem 1.25rem', gap: '1.5rem', flexWrap: 'wrap' }}>
          <label className="stack" style={{ gap: '.3rem', minWidth: 200 }}>
            <span className="eyebrow">Save all of these under</span>
            {isOffice ? (
              <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Subject" />
            ) : (
              <select value={subject} onChange={(e) => setSubject(e.target.value)}>
                <option value="">Select…</option>
                {mySubjects.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            )}
          </label>
          <div className="stack" style={{ gap: '.2rem' }}>
            <span className="eyebrow">Selected</span>
            <span className="mono" style={{ fontSize: '1.5rem', fontWeight: 600 }}>
              {selected}/{drafts.length}
            </span>
          </div>
          <button className="btn-ghost" style={{ alignSelf: 'center' }}
            onClick={() => setDrafts((d) => d.map((x) => ({ ...x, include: selected !== d.length })))}>
            {selected === drafts.length ? 'Deselect all' : 'Select all'}
          </button>
        </section>

        <div className="stack" style={{ gap: '.75rem' }}>
          {drafts.map((d, i) => (
            <div key={i} className="panel stack" style={{
              padding: '1.1rem 1.25rem', gap: '.7rem',
              borderLeft: d.warnings.length ? '3px solid var(--signal)' : undefined,
              opacity: d.include ? 1 : 0.5,
            }}>
              <div className="spread" style={{ gap: '1rem', alignItems: 'flex-start' }}>
                <label className="row" style={{ gap: '.6rem', cursor: 'pointer' }}>
                  <input type="checkbox" checked={d.include} style={{ width: 'auto', margin: 0 }}
                    onChange={(e) => setDraft(i, { include: e.target.checked })} />
                  <span className="mono muted small">from Q{d.source_number}</span>
                </label>
                <div className="row" style={{ gap: '.5rem' }}>
                  <select value={d.kind} onChange={(e) => setDraft(i, { kind: e.target.value })}
                    style={{ width: 'auto', padding: '.25rem .4rem', fontSize: '.8rem' }}>
                    <option value="mcq">MCQ</option>
                    <option value="descriptive">Descriptive</option>
                    <option value="coding">Coding</option>
                  </select>
                  <select value={d.difficulty} onChange={(e) => setDraft(i, { difficulty: e.target.value })}
                    style={{ width: 'auto', padding: '.25rem .4rem', fontSize: '.8rem' }}>
                    <option>easy</option><option>medium</option><option>hard</option>
                  </select>
                  <input type="number" className="mono" min="1" value={d.max_score}
                    onChange={(e) => setDraft(i, { max_score: e.target.value })}
                    style={{ width: 68, padding: '.25rem .4rem', fontSize: '.8rem' }} />
                </div>
              </div>

              <textarea rows={2} value={d.prompt} onChange={(e) => setDraft(i, { prompt: e.target.value })} />

              {d.kind === 'mcq' && (
                <div className="stack" style={{ gap: '.35rem' }}>
                  {d.options.map((opt, oi) => (
                    <label key={oi} className="row" style={{ gap: '.6rem', cursor: 'pointer' }}>
                      <input type="radio" name={`ans-${i}`} checked={d.correct_option === oi}
                        onChange={() => setDraft(i, { correct_option: oi })} style={{ width: 'auto', margin: 0 }} />
                      <span className="mono small muted">{String.fromCharCode(65 + oi)}</span>
                      <input value={opt} onChange={(e) => setDraft(i, {
                        options: d.options.map((o, oj) => (oj === oi ? e.target.value : o)),
                      })} />
                    </label>
                  ))}
                  {d.correct_option === null && (
                    <span className="small" style={{ color: 'var(--signal)' }}>
                      Select which option is correct.
                    </span>
                  )}
                </div>
              )}

              {d.kind === 'descriptive' && (
                <>
                  <textarea rows={3} value={d.reference_answer}
                    placeholder="Reference answer — candidate responses are graded against this"
                    onChange={(e) => setDraft(i, { reference_answer: e.target.value })} />
                  <input value={d.rubric_keywords.join(', ')} placeholder="Rubric keywords, comma separated"
                    onChange={(e) => setDraft(i, {
                      rubric_keywords: e.target.value.split(',').map((k) => k.trim()).filter(Boolean),
                    })} />
                </>
              )}

              {d.kind === 'coding' && (
                <p className="small" style={{ margin: 0, color: 'var(--signal)' }}>
                  Test cases cannot be read from a document. Untick this one and add it from the
                  question bank, where you can write and check the cases.
                </p>
              )}

              {d.warnings.map((w, wi) => (
                <p key={wi} className="small" style={{ margin: 0, color: 'var(--signal)' }}>{w}</p>
              ))}
            </div>
          ))}
        </div>

        <div className="row" style={{ gap: '.6rem' }}>
          <button className="btn-primary" onClick={save} disabled={busy || !selected}>
            {busy ? 'Saving…' : `Save ${selected} question${selected === 1 ? '' : 's'} to the bank`}
          </button>
          <button className="btn-ghost" onClick={() => { setDrafts(null); setError('') }}>Cancel</button>
        </div>
      </div>
    )
  }

  return (
    <div className="stack" style={{ gap: '1.25rem', maxWidth: 780 }}>
      <div>
        <span className="eyebrow">Question bank</span>
        <h1 style={{ marginTop: '.3rem' }}>Import questions</h1>
        <p className="muted small" style={{ marginTop: '.4rem' }}>
          Upload a question paper or paste it in. You will review everything before it is saved.
        </p>
      </div>

      {error && <Banner tone="alert">{error}</Banner>}

      <section className="panel stack" style={{ padding: '1.25rem', gap: '.9rem' }}>
        <h2>Upload a file</h2>
        <p className="small muted" style={{ margin: 0 }}>
          PDF, Word or plain text, up to 5 MB. A scanned PDF holds images rather than text and
          cannot be read — paste those instead.
        </p>
        <div className="row" style={{ gap: '.75rem', flexWrap: 'wrap' }}>
          <input ref={fileInput} type="file" accept=".pdf,.docx,.txt,.md" style={{ width: 'auto', flex: 1 }} />
          <label className="row" style={{ gap: '.4rem' }}>
            <span className="eyebrow">Default marks</span>
            <input type="number" className="mono" min="1" value={defaultMarks}
              onChange={(e) => setDefaultMarks(e.target.value)} style={{ width: 70 }} />
          </label>
          <button className="btn-primary" disabled={busy}
            onClick={() => {
              const file = fileInput.current?.files?.[0]
              if (!file) return setError('Choose a file first.')
              preview(() => api.importFile(file, defaultMarks))
            }}>
            {busy ? 'Reading…' : 'Read file'}
          </button>
        </div>
      </section>

      <section className="panel stack" style={{ padding: '1.25rem', gap: '.9rem' }}>
        <h2>Or paste the questions</h2>
        <textarea rows={10} value={text} onChange={(e) => setText(e.target.value)}
          placeholder={'Q1. What is the time complexity of binary search? [2 marks]\na) O(1)\nb) O(log n)\nAnswer: b\n\nQ2. Explain database normalisation. [8 marks]\nAnswer: Normalisation organises tables to reduce redundancy...\nKeywords: redundancy, dependency, 3NF'} />
        <button className="btn-primary" style={{ alignSelf: 'flex-start' }} disabled={busy}
          onClick={() => preview(() => api.importText(text, defaultMarks))}>
          {busy ? 'Reading…' : 'Read questions'}
        </button>
      </section>

      <section className="panel stack" style={{ padding: '1.1rem 1.25rem', gap: '.4rem' }}>
        <span className="eyebrow">How papers are read</span>
        <p className="small muted" style={{ margin: '0 0 .5rem', lineHeight: 1.7 }}>
          With <span className="mono">GROQ_API_KEY</span> set, a language model reads the paper and
          copes with tables, separate answer keys and unusual numbering. Without one — or if the
          service is unreachable — it falls back to pattern matching, which needs the formatting
          below. Either way you review everything before it saves.
        </p>
        <span className="eyebrow">Patterns the fallback looks for</span>
        <p className="small muted" style={{ margin: 0, lineHeight: 1.7 }}>
          Questions numbered <span className="mono">Q1.</span> or <span className="mono">1)</span> ·
          options lettered <span className="mono">a)</span> to <span className="mono">h)</span> ·
          an <span className="mono">Answer:</span> line giving either a letter or a full response ·
          <span className="mono">Keywords:</span> for rubric terms ·
          <span className="mono">[5 marks]</span> anywhere in the question.
        </p>
      </section>
    </div>
  )
}

function Banner({ tone, children }) {
  const map = { alert: ['var(--alert)', 'var(--alert-10)', '#EBC9C6'] }
  const [fg, bg, border] = map[tone]
  return (
    <div className="small" style={{ color: fg, background: bg, border: `1px solid ${border}`, borderRadius: 'var(--r)', padding: '.6rem .8rem' }}>
      {children}
    </div>
  )
}
