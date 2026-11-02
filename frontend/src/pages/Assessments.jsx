import { useEffect, useState } from 'react'
import { api, getUser } from '../api.js'

/** Examiner view: build papers from the question bank and control who can see them. */
export default function Assessments() {
  const me = getUser()
  const isOffice = me?.role === 'controller'
  const canEdit = (a) => isOffice || a.created_by === me?.id
  const [assessments, setAssessments] = useState([])
  const [questions, setQuestions] = useState([])
  const [editing, setEditing] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = () =>
    Promise.all([api.assessments(), api.questions()])
      .then(([a, q]) => { setAssessments(a); setQuestions(q) })
      .catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  const byId = Object.fromEntries(questions.map((q) => [q.id, q]))

  async function act(fn, message) {
    setError(''); setNotice('')
    try { await fn(); setNotice(message); load() } catch (e) { setError(e.message) }
  }

  if (editing) {
    return (
      <Builder
        assessment={editing === 'new' ? null : editing}
        questions={questions}
        error={error}
        onCancel={() => { setEditing(null); setError('') }}
        onSave={async (payload) => {
          setError('')
          try {
            if (editing === 'new') await api.createAssessment(payload)
            else await api.updateAssessment(editing.id, payload)
            setNotice(editing === 'new' ? 'Assessment created.' : 'Assessment updated.')
            setEditing(null); load()
          } catch (e) { setError(e.message); throw e }
        }}
      />
    )
  }

  return (
    <div className="stack" style={{ gap: '1.5rem' }}>
      <div className="spread" style={{ gap: '1rem', alignItems: 'flex-start' }}>
        <div>
          <span className="eyebrow">{isOffice ? 'Exam office' : 'Your papers'}</span>
          <h1 style={{ marginTop: '.3rem' }}>
            {isOffice ? 'All assessments' : `${me?.full_name}'s assessments`}
          </h1>
          <p className="muted small" style={{ marginTop: '.4rem' }}>
            Unpublished assessments are hidden from candidates.
            {isOffice
              ? ' As the exam office you can see every examiner\'s papers.'
              : ' You can only build papers from your own questions.'}
          </p>
        </div>
        <button className="btn-primary" onClick={() => setEditing('new')} disabled={!questions.length}>
          New assessment
        </button>
      </div>

      {error && <Banner tone="alert">{error}</Banner>}
      {notice && <Banner tone="verdict">{notice}</Banner>}
      {!questions.length && <Banner tone="signal">Add questions to the bank first — an assessment needs at least one.</Banner>}

      <div className="stack" style={{ gap: '.6rem' }}>
        {assessments.map((a) => {
          const marks = (a.question_ids || []).reduce((sum, id) => sum + (byId[id]?.max_score || 0), 0)
          return (
            <div key={a.id} className="panel" style={{ padding: '1.1rem 1.25rem' }}>
              <div className="spread" style={{ gap: '1rem', alignItems: 'flex-start' }}>
                <div style={{ flex: 1 }}>
                  <div className="row" style={{ gap: '.6rem', marginBottom: '.35rem', flexWrap: 'wrap' }}>
                    <h2>{a.title}</h2>
                    {a.mode === 'adaptive' && <span className="tag tag-primary">adaptive</span>}
                    <span className={`tag ${a.is_published ? 'tag-verdict' : 'tag-signal'}`}>
                      {a.is_published ? 'published' : 'draft'}
                    </span>
                  </div>
                  <p className="small muted" style={{ margin: '0 0 .4rem' }}>{a.description || 'No description.'}</p>
                  <span className="mono small muted">
                    {a.question_ids.length} questions · {marks} marks · {a.duration_minutes} min
                  </span>
                  {isOffice && a.author_name && (
                    <span className="small muted" style={{ marginLeft: '.6rem' }}>· {a.author_name}</span>
                  )}
                </div>
                <div className="row" style={{ gap: '.5rem', flexShrink: 0 }}>
                  {!canEdit(a) && <span className="small muted" style={{ whiteSpace: 'nowrap' }}>read only</span>}
                  {canEdit(a) && <>
                  <button className="btn-ghost" onClick={() => setEditing(a)}>Edit</button>
                  <button className="btn-ghost" onClick={() => act(() => api.togglePublish(a.id), a.is_published ? 'Unpublished.' : 'Published.')}>
                    {a.is_published ? 'Unpublish' : 'Publish'}
                  </button>
                  <button
                    className="btn-ghost" style={{ color: 'var(--alert)' }}
                    onClick={() => confirm(`Delete "${a.title}"?`) && act(() => api.deleteAssessment(a.id), 'Assessment deleted.')}
                  >
                    Delete
                  </button></>}
                </div>
              </div>
            </div>
          )
        })}
        {!assessments.length && (
          <div className="panel" style={{ padding: '2.5rem', textAlign: 'center' }}>
            <p style={{ margin: 0, fontWeight: 500 }}>No assessments yet</p>
          </div>
        )}
      </div>
    </div>
  )
}

function Builder({ assessment, questions, onCancel, onSave, error }) {
  const [title, setTitle] = useState(assessment?.title || '')
  const [description, setDescription] = useState(assessment?.description || '')
  const [duration, setDuration] = useState(assessment?.duration_minutes || 45)
  const [mode, setMode] = useState(assessment?.mode || 'fixed')
  const [maxQ, setMaxQ] = useState(assessment?.adaptive_max_questions || 10)
  const [targetSE, setTargetSE] = useState(assessment?.adaptive_target_se ?? 0.4)
  const [picked, setPicked] = useState(assessment?.question_ids || [])
  const [localError, setLocalError] = useState('')
  const [saving, setSaving] = useState(false)

  // Filters on the picker, not constraints on the paper. An examiner setting a
  // single-type single-difficulty paper should not have to read past questions
  // that cannot belong in it, but nothing stops a deliberately mixed paper.
  const [filterKind, setFilterKind] = useState('')
  const [filterDifficulty, setFilterDifficulty] = useState('')

  const toggle = (id) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]))
  const visible = questions.filter(
    (q) => (!filterKind || q.kind === filterKind) && (!filterDifficulty || q.difficulty === filterDifficulty)
  )
  const chosenQs = questions.filter((q) => picked.includes(q.id))
  const kinds = [...new Set(chosenQs.map((q) => q.kind))]
  const difficulties = [...new Set(chosenQs.map((q) => q.difficulty))]
  const marks = picked.reduce((sum, id) => sum + (questions.find((q) => q.id === id)?.max_score || 0), 0)

  async function submit() {
    setLocalError('')
    if (!title.trim()) return setLocalError('Give the assessment a title.')
    if (!picked.length) return setLocalError('Select at least one question.')
    setSaving(true)
    try {
      await onSave({
        title: title.trim(), description: description.trim(),
        duration_minutes: Number(duration), question_ids: picked,
        mode, adaptive_max_questions: Number(maxQ), adaptive_target_se: Number(targetSE),
      })
    } catch { /* parent shows it */ } finally { setSaving(false) }
  }

  return (
    <div className="stack" style={{ gap: '1.25rem', maxWidth: 780 }}>
      <div>
        <button className="eyebrow" style={{ background: 'none', border: 'none', padding: 0 }} onClick={onCancel}>← Assessments</button>
        <h1 style={{ marginTop: '.4rem' }}>{assessment ? 'Edit assessment' : 'New assessment'}</h1>
      </div>

      {(error || localError) && <Banner tone="alert">{error || localError}</Banner>}

      <section className="panel stack" style={{ padding: '1.25rem', gap: '.9rem' }}>
        <label className="stack" style={{ gap: '.3rem' }}>
          <span className="eyebrow">Title</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Backend Engineer Screening" />
        </label>
        <label className="stack" style={{ gap: '.3rem' }}>
          <span className="eyebrow">Description</span>
          <textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <label className="stack" style={{ gap: '.3rem', maxWidth: 180 }}>
          <span className="eyebrow">Duration (minutes)</span>
          <input type="number" className="mono" min="1" value={duration} onChange={(e) => setDuration(e.target.value)} />
        </label>
      </section>

      <section className="panel stack" style={{ padding: '1.25rem', gap: '.9rem' }}>
        <h2>How questions are served</h2>
        <div className="row" style={{ gap: '.5rem' }}>
          {[
            ['fixed', 'Fixed paper', 'Everyone sits the same questions and can move between them freely.'],
            ['adaptive', 'Adaptive', 'Each question is chosen from how the candidate is performing. No going back.'],
          ].map(([id, label]) => (
            <button key={id} onClick={() => setMode(id)}
              style={{
                border: `1px solid ${mode === id ? 'var(--primary)' : 'var(--rule)'}`,
                background: mode === id ? 'var(--primary-10)' : 'transparent',
                color: mode === id ? 'var(--primary)' : 'var(--ink-2)',
                fontWeight: mode === id ? 600 : 500,
              }}>
              {label}
            </button>
          ))}
        </div>
        <p className="small muted" style={{ margin: 0 }}>
          {mode === 'adaptive'
            ? 'The questions below become a pool. Each candidate is served a different sequence from it, so the paper measures ability in fewer questions than a fixed one needs.'
            : 'Everyone sits the same questions and can move between them freely.'}
        </p>

        {mode === 'adaptive' && (
          <div className="row" style={{ gap: '1rem', flexWrap: 'wrap' }}>
            <label className="stack" style={{ gap: '.3rem', maxWidth: 170 }}>
              <span className="eyebrow">Maximum questions</span>
              <input type="number" className="mono" min="3" value={maxQ} onChange={(e) => setMaxQ(e.target.value)} />
            </label>
            <label className="stack" style={{ gap: '.3rem', maxWidth: 210 }}>
              <span className="eyebrow">Stop when precision reaches</span>
              <input type="number" className="mono" step="0.05" min="0.15" max="1"
                value={targetSE} onChange={(e) => setTargetSE(e.target.value)} />
              <span className="small muted">Lower is stricter and asks more questions.</span>
            </label>
          </div>
        )}
      </section>

      <section className="panel stack" style={{ padding: '1.25rem', gap: '.6rem' }}>
        <div className="spread">
          <h2>Questions</h2>
          <span className="mono small muted">{picked.length} selected · {marks} marks</span>
        </div>

        <div className="row" style={{ gap: '.5rem', flexWrap: 'wrap' }}>
          <select value={filterKind} onChange={(e) => setFilterKind(e.target.value)}
            style={{ width: 'auto', fontSize: '.85rem' }}>
            <option value="">All types</option>
            <option value="mcq">Multiple choice only</option>
            <option value="descriptive">Written only</option>
            <option value="coding">Coding only</option>
          </select>
          <select value={filterDifficulty} onChange={(e) => setFilterDifficulty(e.target.value)}
            style={{ width: 'auto', fontSize: '.85rem' }}>
            <option value="">All difficulties</option>
            <option value="easy">Easy only</option>
            <option value="medium">Medium only</option>
            <option value="hard">Hard only</option>
          </select>
          {(filterKind || filterDifficulty) && (
            <button className="btn-ghost" style={{ fontSize: '.8rem', padding: '.35rem .7rem' }}
              onClick={() => { setFilterKind(''); setFilterDifficulty('') }}>
              Clear
            </button>
          )}
          <span className="small muted" style={{ marginLeft: 'auto' }}>
            showing {visible.length} of {questions.length}
          </span>
        </div>

        {picked.length > 1 && (kinds.length > 1 || difficulties.length > 1) && (
          <p className="small muted" style={{ margin: 0 }}>
            This paper mixes {kinds.length > 1 ? kinds.join(' and ') : ''}
            {kinds.length > 1 && difficulties.length > 1 ? ', and ' : ''}
            {difficulties.length > 1 ? `${difficulties.join(' and ')} difficulty` : ''}.
            That is allowed — filter above if you meant it to be uniform.
          </p>
        )}
        {visible.map((q) => {
          const on = picked.includes(q.id)
          return (
            <label key={q.id} className="row" style={{
              gap: '.7rem', padding: '.6rem .75rem', cursor: 'pointer', alignItems: 'flex-start',
              border: `1px solid ${on ? 'var(--primary)' : 'var(--rule)'}`,
              background: on ? 'var(--primary-10)' : 'transparent', borderRadius: 'var(--r)',
            }}>
              <input type="checkbox" checked={on} onChange={() => toggle(q.id)} style={{ width: 'auto', margin: '.25rem 0 0' }} />
              <div style={{ flex: 1 }}>
                <div className="row" style={{ gap: '.45rem', flexWrap: 'wrap', marginBottom: '.2rem' }}>
                  <span className="mono small muted">#{q.id}</span>
                  <span className="tag tag-primary">{q.kind}</span>
                  <span className="small muted">{q.skill} · {q.difficulty} · {q.max_score} marks</span>
                </div>
                <span className="small">{q.prompt.slice(0, 110)}{q.prompt.length > 110 ? '…' : ''}</span>
              </div>
            </label>
          )
        })}
      </section>

      <div className="row" style={{ gap: '.6rem' }}>
        <button className="btn-primary" onClick={submit} disabled={saving}>
          {saving ? 'Saving…' : assessment ? 'Save changes' : 'Create assessment'}
        </button>
        <button className="btn-ghost" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  )
}

/** Inline notice. Colour lives in the stylesheet so both themes stay correct. */
function Banner({ tone, children }) {
  return <div className={`notice notice-${tone}`}>{children}</div>
}
