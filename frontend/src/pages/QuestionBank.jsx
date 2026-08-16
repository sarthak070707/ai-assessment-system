import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, getUser } from '../api.js'
import QuestionEditor from '../components/QuestionEditor.jsx'

const KINDS = ['mcq', 'coding', 'descriptive']

export default function QuestionBank() {
  const me = getUser()
  const isOffice = me?.role === 'controller'
  const [questions, setQuestions] = useState([])
  const [editing, setEditing] = useState(null)   // question object, or 'new'
  const [filter, setFilter] = useState({ kind: '', skill: '' })
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = () => api.questions().then(setQuestions).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  const skills = useMemo(
    () => [...new Set(questions.map((q) => q.skill))].sort(),
    [questions]
  )
  const visible = questions.filter(
    (q) => (!filter.kind || q.kind === filter.kind) && (!filter.skill || q.skill === filter.skill)
  )

  async function remove(question) {
    if (!confirm(`Delete this question?\n\n"${question.prompt.slice(0, 80)}"`)) return
    setError(''); setNotice('')
    try {
      await api.deleteQuestion(question.id)
      setNotice('Question deleted.')
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  async function save(payload) {
    setError(''); setNotice('')
    try {
      if (editing === 'new') {
        await api.createQuestion(payload)
        setNotice('Question added to the bank.')
      } else {
        await api.updateQuestion(editing.id, payload)
        setNotice('Question updated. Scores already awarded are unchanged.')
      }
      setEditing(null)
      load()
    } catch (e) {
      setError(e.message)
      throw e   // keeps the editor open so the examiner can correct it
    }
  }

  if (editing) {
    return (
      <QuestionEditor
        question={editing === 'new' ? null : editing}
        onCancel={() => { setEditing(null); setError('') }}
        onSave={save}
        error={error}
      />
    )
  }

  return (
    <div className="stack" style={{ gap: '1.5rem' }}>
      <div className="spread" style={{ gap: '1rem', alignItems: 'flex-start' }}>
        <div>
          <span className="eyebrow">{isOffice ? 'Exam office' : 'Your question bank'}</span>
          <h1 style={{ marginTop: '.3rem' }}>
            {isOffice ? 'All questions' : `${me?.full_name}'s questions`}
          </h1>
          <p className="muted small" style={{ marginTop: '.4rem' }}>
            {questions.length} question{questions.length === 1 ? '' : 's'} across {skills.length} skill
            {skills.length === 1 ? '' : 's'}.{' '}
            {isOffice
              ? 'Every examiner\'s questions, with their author.'
              : `You write within ${(me?.subjects || []).join(' and ') || 'no assigned subject'}. Only you and the exam office can see these.`}
          </p>
        </div>
        <div className="row" style={{ gap: '.5rem' }}>
          <Link to="/questions/import"><button className="btn-ghost">Import from paper</button></Link>
          <button className="btn-primary" onClick={() => setEditing('new')}>New question</button>
        </div>
      </div>

      {error && <Banner tone="alert">{error}</Banner>}
      {notice && <Banner tone="verdict">{notice}</Banner>}

      <div className="row" style={{ gap: '.6rem', flexWrap: 'wrap' }}>
        <Chip active={!filter.kind && !filter.skill} onClick={() => setFilter({ kind: '', skill: '' })}>
          All
        </Chip>
        {KINDS.map((k) => (
          <Chip key={k} active={filter.kind === k} onClick={() => setFilter((f) => ({ ...f, kind: f.kind === k ? '' : k }))}>
            {k}
          </Chip>
        ))}
        <span style={{ width: 1, height: 22, background: 'var(--rule)' }} />
        {skills.map((s) => (
          <Chip key={s} active={filter.skill === s} onClick={() => setFilter((f) => ({ ...f, skill: f.skill === s ? '' : s }))}>
            {s}
          </Chip>
        ))}
      </div>

      <div className="stack" style={{ gap: '.6rem' }}>
        {visible.map((q) => (
          <div key={q.id} className="panel" style={{ padding: '1rem 1.15rem' }}>
            <div className="spread" style={{ gap: '1rem', alignItems: 'flex-start' }}>
              <div style={{ flex: 1 }}>
                <div className="row" style={{ gap: '.5rem', flexWrap: 'wrap', marginBottom: '.45rem' }}>
                  <span className="mono muted small">#{q.id}</span>
                  <span className="tag tag-primary">{q.kind}</span>
                  <span className="tag" style={{ borderColor: 'var(--rule)', color: 'var(--ink-3)' }}>{q.skill}</span>
                  <span className="tag" style={{ borderColor: 'var(--rule)', color: 'var(--ink-3)' }}>{q.difficulty}</span>
                  <span className="mono small muted">{q.max_score} marks</span>
                </div>
                <p style={{ margin: 0 }}>{q.prompt}</p>
                <p className="small muted" style={{ margin: '.4rem 0 0' }}>
                  {summarise(q)}
                  {isOffice && q.author_name && <> · {q.author_name}</>}
                </p>
              </div>
              <div className="row" style={{ gap: '.5rem', flexShrink: 0 }}>
                <button className="btn-ghost" onClick={() => setEditing(q)}>Edit</button>
                <button className="btn-ghost" style={{ color: 'var(--alert)' }} onClick={() => remove(q)}>Delete</button>
              </div>
            </div>
          </div>
        ))}

        {!visible.length && (
          <div className="panel" style={{ padding: '2.5rem', textAlign: 'center' }}>
            <p style={{ margin: 0, fontWeight: 500 }}>
              {questions.length ? 'No questions match that filter' : 'You have not written any questions yet'}
            </p>
            <p className="muted small" style={{ margin: '.35rem 0 0' }}>
              {questions.length ? 'Clear the filter to see everything.' : 'Questions you add are visible only to you and the exam office.'}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

function summarise(q) {
  if (q.kind === 'mcq') {
    const answer = q.options?.[q.correct_option]
    return `${q.options?.length ?? 0} options · answer: ${answer ?? '—'}`
  }
  if (q.kind === 'coding') {
    const hidden = (q.test_cases || []).filter((c) => c.hidden).length
    return `${q.test_cases?.length ?? 0} test cases (${hidden} hidden)`
  }
  const words = (q.reference_answer || '').split(/\s+/).filter(Boolean).length
  return `reference answer ${words} words · ${q.rubric_keywords?.length ?? 0} rubric keywords`
}

function Chip({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className="mono"
      style={{
        fontSize: '.72rem', letterSpacing: '.04em', textTransform: 'uppercase',
        padding: '.3rem .6rem',
        border: `1px solid ${active ? 'var(--primary)' : 'var(--rule)'}`,
        background: active ? 'var(--primary)' : 'transparent',
        color: active ? '#fff' : 'var(--ink-2)',
      }}
    >
      {children}
    </button>
  )
}

function Banner({ tone, children }) {
  const map = {
    alert: ['var(--alert)', 'var(--alert-10)', '#EBC9C6'],
    verdict: ['var(--verdict)', 'var(--verdict-10)', '#BFDED3'],
  }
  const [fg, bg, border] = map[tone]
  return (
    <div className="small" style={{ color: fg, background: bg, border: `1px solid ${border}`, borderRadius: 'var(--r)', padding: '.6rem .8rem' }}>
      {children}
    </div>
  )
}
