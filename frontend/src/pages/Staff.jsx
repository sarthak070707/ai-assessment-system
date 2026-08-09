import { useEffect, useState } from 'react'
import { api } from '../api.js'

/** Exam-office view: create professor accounts and manage their access. */
export default function Staff() {
  const [staff, setStaff] = useState([])
  const [form, setForm] = useState({ staff_id: '', full_name: '', department: '', subjects: '', role: 'examiner' })
  const [editingSubjects, setEditingSubjects] = useState(null)
  const [issued, setIssued] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = () => api.staff().then(setStaff).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  async function create() {
    setError(''); setNotice(''); setIssued(null)
    if (!form.staff_id.trim()) return setError('A staff ID is required.')
    try {
      const result = await api.createStaff({
        ...form,
        staff_id: form.staff_id.trim().toUpperCase(),
        subjects: form.subjects.split(',').map((x) => x.trim()).filter(Boolean),
      })
      setIssued(result)
      setForm({ staff_id: '', full_name: '', department: '', subjects: '', role: 'examiner' })
      load()
    } catch (e) { setError(e.message) }
  }

  async function reset(member) {
    setError(''); setNotice(''); setIssued(null)
    if (!confirm(`Issue a new temporary password for ${member.full_name}? Their current one stops working.`)) return
    try {
      setIssued(await api.resetStaffPassword(member.id))
      load()
    } catch (e) { setError(e.message) }
  }

  async function toggle(member) {
    setError(''); setNotice('')
    try {
      await api.toggleStaffActive(member.id)
      setNotice(`${member.full_name} ${member.is_active ? 'deactivated' : 'reactivated'}.`)
      load()
    } catch (e) { setError(e.message) }
  }

  return (
    <div className="stack" style={{ gap: '1.5rem' }}>
      <div>
        <span className="eyebrow">Exam office</span>
        <h1 style={{ marginTop: '.3rem' }}>Staff accounts</h1>
        <p className="muted small" style={{ marginTop: '.4rem' }}>
          Examiners own the questions and papers they create. The exam office can see and change everything.
        </p>
      </div>

      {error && <Banner tone="alert">{error}</Banner>}
      {notice && <Banner tone="verdict">{notice}</Banner>}

      {issued && (
        <section className="panel stack" style={{ padding: '1.25rem', gap: '.5rem', borderLeft: '3px solid var(--signal)' }}>
          <span className="eyebrow" style={{ color: '#8A5610' }}>Temporary password</span>
          <p className="small" style={{ margin: 0 }}>
            Give this to <strong>{issued.full_name}</strong> ({issued.staff_id}). They must change it on
            first sign-in. It is shown once and cannot be looked up again.
          </p>
          <div className="mono" style={{ fontSize: '1.3rem', fontWeight: 600, letterSpacing: '.05em', padding: '.5rem 0' }}>
            {issued.temporary_password}
          </div>
          <button className="btn-ghost" style={{ alignSelf: 'flex-start' }}
            onClick={() => navigator.clipboard?.writeText(issued.temporary_password)}>
            Copy
          </button>
        </section>
      )}

      <section className="panel stack" style={{ padding: '1.25rem', gap: '.75rem' }}>
        <h2>Add a staff member</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr 1.5fr 1fr', gap: '.6rem' }}>
          <Field label="Staff ID">
            <input className="mono" value={form.staff_id} placeholder="CS412"
              onChange={(e) => setForm((f) => ({ ...f, staff_id: e.target.value.toUpperCase() }))} />
          </Field>
          <Field label="Full name">
            <input value={form.full_name} placeholder="Dr. Anjali Verma"
              onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))} />
          </Field>
          <Field label="Department">
            <input value={form.department} placeholder="Computer Science"
              onChange={(e) => setForm((f) => ({ ...f, department: e.target.value }))} />
          </Field>
          <Field label="Role">
            <select value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}>
              <option value="examiner">Examiner</option>
              <option value="controller">Exam office</option>
            </select>
          </Field>
        </div>
        <Field label="Subjects they teach">
          <input
            value={form.subjects} placeholder="Algorithms, Data Structures"
            onChange={(e) => setForm((f) => ({ ...f, subjects: e.target.value }))}
          />
        </Field>
        <p className="small muted" style={{ margin: 0 }}>
          Comma separated. An examiner can only write questions inside these subjects.
        </p>
        <button className="btn-primary" style={{ alignSelf: 'flex-start' }} onClick={create}>
          Create account
        </button>
      </section>

      <div className="stack" style={{ gap: '.6rem' }}>
        <h2>Current staff</h2>
        {staff.map((m) => (
          <div key={m.id} className="panel spread" style={{ padding: '.9rem 1.15rem', opacity: m.is_active ? 1 : 0.55 }}>
            <div>
              <div className="row" style={{ gap: '.6rem', flexWrap: 'wrap' }}>
                <span className="mono" style={{ fontWeight: 600 }}>{m.staff_id}</span>
                <span style={{ fontWeight: 500 }}>{m.full_name}</span>
                <span className={`tag ${m.role === 'controller' ? 'tag-primary' : ''}`}
                  style={m.role !== 'controller' ? { borderColor: 'var(--rule)', color: 'var(--ink-3)' } : {}}>
                  {m.role === 'controller' ? 'exam office' : 'examiner'}
                </span>
                {!m.is_active && <span className="tag tag-alert">deactivated</span>}
                {m.must_change_password && <span className="tag tag-signal">password not set</span>}
              </div>
              <div className="row" style={{ gap: '.35rem', flexWrap: 'wrap', marginTop: '.3rem' }}>
                {(m.subjects || []).map((s) => (
                  <span key={s} className="tag" style={{ borderColor: 'var(--rule)', color: 'var(--ink-3)' }}>{s}</span>
                ))}
                {m.role === 'examiner' && !(m.subjects || []).length && (
                  <span className="tag tag-signal">no subjects assigned</span>
                )}
              </div>
              <span className="small muted">
                {m.department || 'No department'}
                {m.last_login_at && ` · last signed in ${new Date(m.last_login_at).toLocaleDateString()}`}
              </span>
              {editingSubjects === m.id && (
                <div className="row" style={{ gap: '.5rem', marginTop: '.5rem' }}>
                  <input
                    defaultValue={(m.subjects || []).join(', ')}
                    id={`subj-${m.id}`}
                    placeholder="Algorithms, Data Structures"
                  />
                  <button className="btn-primary" onClick={async () => {
                    const raw = document.getElementById(`subj-${m.id}`).value
                    try {
                      await api.updateStaff(m.id, { subjects: raw.split(',').map((x) => x.trim()).filter(Boolean) })
                      setEditingSubjects(null); setNotice('Subjects updated.'); load()
                    } catch (e) { setError(e.message) }
                  }}>Save</button>
                  <button className="btn-ghost" onClick={() => setEditingSubjects(null)}>Cancel</button>
                </div>
              )}
            </div>
            <div className="row" style={{ gap: '.5rem' }}>
              {m.role === 'examiner' && (
                <button className="btn-ghost" onClick={() => setEditingSubjects(editingSubjects === m.id ? null : m.id)}>
                  Subjects
                </button>
              )}
              <button className="btn-ghost" onClick={() => reset(m)}>Reset password</button>
              <button className="btn-ghost" style={{ color: m.is_active ? 'var(--alert)' : 'var(--verdict)' }}
                onClick={() => toggle(m)}>
                {m.is_active ? 'Deactivate' : 'Reactivate'}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <label className="stack" style={{ gap: '.3rem' }}>
      <span className="eyebrow">{label}</span>
      {children}
    </label>
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
