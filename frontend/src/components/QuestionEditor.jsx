import { useState } from 'react'
import { getUser } from '../api.js'

const KINDS = [
  { id: 'mcq', label: 'Multiple choice', hint: 'Graded by exact match against the correct option.' },
  { id: 'coding', label: 'Coding', hint: 'Graded by running the submission against test cases, plus a structural review.' },
  { id: 'descriptive', label: 'Descriptive', hint: 'Graded by comparing meaning against a reference answer. Uncertain scores go to review.' },
]
const DIFFICULTIES = ['easy', 'medium', 'hard']

const BLANK = {
  kind: 'mcq', skill: '', difficulty: 'medium', prompt: '', max_score: 10,
  options: ['', ''], correct_option: 0,
  starter_code: '', test_cases: [],
  reference_answer: '', rubric_keywords: [],
}

/** Test cases hold JSON, so they are edited as text and parsed on save. */
function toDraftCases(cases) {
  return (cases || []).map((c) => ({
    name: c.name || '',
    entrypoint: c.entrypoint || 'solve',
    input: JSON.stringify(c.input ?? []),
    expected: JSON.stringify(c.expected ?? null),
    hidden: !!c.hidden,
  }))
}

export default function QuestionEditor({ question, onCancel, onSave, error }) {
  const me = getUser()
  const isOffice = me?.role === 'controller'
  const mySubjects = me?.subjects || []
  const [form, setForm] = useState(() => ({
    ...BLANK,
    ...(question || {}),
    options: question?.options?.length ? question.options : BLANK.options,
    rubric_keywords: question?.rubric_keywords || [],
  }))
  const [cases, setCases] = useState(() => toDraftCases(question?.test_cases))
  const [keywords, setKeywords] = useState(() => (question?.rubric_keywords || []).join(', '))
  const [localError, setLocalError] = useState('')
  const [saving, setSaving] = useState(false)

  const set = (patch) => setForm((f) => ({ ...f, ...patch }))
  const kind = form.kind

  function addCase() {
    setCases((c) => [...c, { name: `Case ${c.length + 1}`, entrypoint: 'solve', input: '[]', expected: 'null', hidden: false }])
  }
  function setCase(i, patch) {
    setCases((c) => c.map((row, j) => (j === i ? { ...row, ...patch } : row)))
  }

  async function submit() {
    setLocalError('')

    const payload = {
      kind, skill: form.skill.trim(), difficulty: form.difficulty,
      prompt: form.prompt.trim(), max_score: Number(form.max_score),
      options: null, correct_option: null,
      starter_code: null, test_cases: null,
      reference_answer: null, rubric_keywords: null,
    }

    if (!payload.skill) return setLocalError('Choose the subject this question belongs to.')

    if (kind === 'mcq') {
      payload.options = form.options.map((o) => o.trim()).filter(Boolean)
      payload.correct_option = Number(form.correct_option)
      if (payload.correct_option >= payload.options.length) {
        return setLocalError('The option marked correct was left blank.')
      }
    }

    if (kind === 'coding') {
      payload.starter_code = form.starter_code || ''
      try {
        payload.test_cases = cases.map((c, i) => {
          const label = c.name || `Case ${i + 1}`
          let input, expected
          try { input = JSON.parse(c.input) } catch { throw new Error(`${label}: input is not valid JSON. Use e.g. [[2,7,11,15], 9]`) }
          try { expected = JSON.parse(c.expected) } catch { throw new Error(`${label}: expected output is not valid JSON. Use e.g. [0,1] or 3 or "text"`) }
          if (!Array.isArray(input)) throw new Error(`${label}: input must be a JSON array of arguments, e.g. [5] for solve(5).`)
          return { name: label, entrypoint: c.entrypoint.trim() || 'solve', input, expected, hidden: c.hidden }
        })
      } catch (e) {
        return setLocalError(e.message)
      }
      if (!payload.test_cases.length) return setLocalError('Add at least one test case, or the grader has nothing to check.')
    }

    if (kind === 'descriptive') {
      payload.reference_answer = form.reference_answer.trim()
      payload.rubric_keywords = keywords.split(',').map((k) => k.trim()).filter(Boolean)
    }

    setSaving(true)
    try { await onSave(payload) } catch { /* parent shows the error */ } finally { setSaving(false) }
  }

  const shown = error || localError

  return (
    <div className="stack" style={{ gap: '1.25rem', maxWidth: 780 }}>
      <div>
        <button className="eyebrow" style={{ background: 'none', border: 'none', padding: 0 }} onClick={onCancel}>
          ← Question bank
        </button>
        <h1 style={{ marginTop: '.4rem' }}>{question ? `Edit question #${question.id}` : 'New question'}</h1>
      </div>

      {shown && (
        <div className="notice notice-alert">{shown}</div>
      )}

      <section className="panel stack" style={{ padding: '1.25rem', gap: '1rem' }}>
        <div className="stack" style={{ gap: '.5rem' }}>
          <span className="eyebrow">Type</span>
          <div className="row" style={{ gap: '.5rem', flexWrap: 'wrap' }}>
            {KINDS.map((k) => (
              <button
                key={k.id}
                onClick={() => set({ kind: k.id })}
                style={{
                  border: `1px solid ${kind === k.id ? 'var(--primary)' : 'var(--rule)'}`,
                  background: kind === k.id ? 'var(--primary-10)' : 'transparent',
                  color: kind === k.id ? 'var(--primary)' : 'var(--ink-2)',
                  fontWeight: kind === k.id ? 600 : 500,
                }}
              >
                {k.label}
              </button>
            ))}
          </div>
          <p className="small muted" style={{ margin: 0 }}>{KINDS.find((k) => k.id === kind).hint}</p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: '.75rem' }}>
          <Field
            label="Subject"
            hint={isOffice ? 'Any subject' : `You teach ${mySubjects.join(', ') || 'nothing yet'}`}
          >
            {isOffice ? (
              <input value={form.skill} onChange={(e) => set({ skill: e.target.value })} placeholder="e.g. Databases" />
            ) : (
              <select value={form.skill} onChange={(e) => set({ skill: e.target.value })}>
                <option value="">Select…</option>
                {mySubjects.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            )}
          </Field>
          <Field label="Difficulty">
            <select value={form.difficulty} onChange={(e) => set({ difficulty: e.target.value })}>
              {DIFFICULTIES.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </Field>
          <Field label="Marks">
            <input type="number" className="mono" min="1" step="1" value={form.max_score} onChange={(e) => set({ max_score: e.target.value })} />
          </Field>
        </div>

        <Field label="Question">
          <textarea rows={3} value={form.prompt} onChange={(e) => set({ prompt: e.target.value })} placeholder="What the candidate sees." />
        </Field>
      </section>

      {kind === 'mcq' && (
        <section className="panel stack" style={{ padding: '1.25rem', gap: '.75rem' }}>
          <div className="spread">
            <h2>Options</h2>
            <span className="small muted">Select the correct answer</span>
          </div>
          {form.options.map((opt, i) => (
            <div key={i} className="row" style={{ gap: '.65rem' }}>
              <input
                type="radio" name="correct" checked={Number(form.correct_option) === i}
                onChange={() => set({ correct_option: i })} style={{ width: 'auto', margin: 0 }}
                aria-label={`Mark option ${String.fromCharCode(65 + i)} correct`}
              />
              <span className="mono small muted" style={{ width: 14 }}>{String.fromCharCode(65 + i)}</span>
              <input
                value={opt}
                onChange={(e) => set({ options: form.options.map((o, j) => (j === i ? e.target.value : o)) })}
                placeholder={`Option ${String.fromCharCode(65 + i)}`}
              />
              {form.options.length > 2 && (
                <button className="btn-ghost" onClick={() => set({
                  options: form.options.filter((_, j) => j !== i),
                  correct_option: Number(form.correct_option) >= i && Number(form.correct_option) > 0
                    ? Number(form.correct_option) - 1 : form.correct_option,
                })}>Remove</button>
              )}
            </div>
          ))}
          <button className="btn-ghost" style={{ alignSelf: 'flex-start' }} onClick={() => set({ options: [...form.options, ''] })}>
            Add option
          </button>
        </section>
      )}

      {kind === 'coding' && (
        <>
          <section className="panel stack" style={{ padding: '1.25rem', gap: '.6rem' }}>
            <h2>Starter code</h2>
            <p className="small muted" style={{ margin: 0 }}>Pre-filled in the candidate's editor. Optional.</p>
            <textarea className="code" rows={5} value={form.starter_code || ''} spellCheck="false"
              onChange={(e) => set({ starter_code: e.target.value })}
              placeholder={'def solve(nums, target):\n    pass'} />
          </section>

          <section className="panel stack" style={{ padding: '1.25rem', gap: '.75rem' }}>
            <div className="spread">
              <h2>Test cases</h2>
              <button className="btn-ghost" onClick={addCase}>Add test case</button>
            </div>
            <p className="small muted" style={{ margin: 0 }}>
              Input is a JSON array of arguments — <span className="mono">[[2,7,11,15], 9]</span> calls{' '}
              <span className="mono">solve([2,7,11,15], 9)</span>. Hidden cases are not shown to the candidate.
            </p>

            {cases.map((c, i) => (
              <div key={i} className="stack" style={{ gap: '.5rem', padding: '.85rem', border: '1px solid var(--rule)', borderRadius: 'var(--r)' }}>
                <div className="row" style={{ gap: '.5rem' }}>
                  <input value={c.name} onChange={(e) => setCase(i, { name: e.target.value })} placeholder="Case name" style={{ flex: 2 }} />
                  <input className="mono" value={c.entrypoint} onChange={(e) => setCase(i, { entrypoint: e.target.value })} placeholder="function" style={{ flex: 1 }} />
                  <label className="row small" style={{ gap: '.35rem', whiteSpace: 'nowrap' }}>
                    <input type="checkbox" checked={c.hidden} onChange={(e) => setCase(i, { hidden: e.target.checked })} style={{ width: 'auto', margin: 0 }} />
                    Hidden
                  </label>
                  <button className="btn-ghost" style={{ color: 'var(--alert)' }} onClick={() => setCases((cs) => cs.filter((_, j) => j !== i))}>
                    Remove
                  </button>
                </div>
                <div className="grid-2" style={{ gap: '.5rem' }}>
                  <Field label="Input (JSON array)">
                    <input className="mono" value={c.input} onChange={(e) => setCase(i, { input: e.target.value })} placeholder="[[2,7,11,15], 9]" />
                  </Field>
                  <Field label="Expected output (JSON)">
                    <input className="mono" value={c.expected} onChange={(e) => setCase(i, { expected: e.target.value })} placeholder="[0,1]" />
                  </Field>
                </div>
              </div>
            ))}

            {!cases.length && <p className="small muted" style={{ margin: 0 }}>No test cases yet — the grader needs at least one.</p>}
          </section>
        </>
      )}

      {kind === 'descriptive' && (
        <section className="panel stack" style={{ padding: '1.25rem', gap: '1rem' }}>
          <Field label="Reference answer" hint="Candidate answers are compared against this by meaning, not wording">
            <textarea rows={6} value={form.reference_answer || ''} onChange={(e) => set({ reference_answer: e.target.value })}
              placeholder="A complete, well-written answer worth full marks." />
          </Field>
          <Field label="Rubric keywords" hint="Comma separated. Concepts the answer must mention to earn full marks">
            <input value={keywords} onChange={(e) => setKeywords(e.target.value)} placeholder="b-tree, full table scan, write, storage" />
          </Field>
        </section>
      )}

      <div className="row" style={{ gap: '.6rem' }}>
        <button className="btn-primary" onClick={submit} disabled={saving}>
          {saving ? 'Saving…' : question ? 'Save changes' : 'Add to question bank'}
        </button>
        <button className="btn-ghost" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  )
}

function Field({ label, hint, children }) {
  return (
    <label className="stack" style={{ gap: '.3rem' }}>
      <span className="eyebrow">{label}</span>
      {children}
      {hint && <span className="small muted">{hint}</span>}
    </label>
  )
}
