import { useEffect, useState } from 'react'
import { api } from '../api.js'

/** Enrol candidates and issue the single-use codes that admit them to a paper. */
export default function Candidates() {
  const [candidates, setCandidates] = useState([])
  const [assessments, setAssessments] = useState([])
  const [codes, setCodes] = useState([])
  const [chosen, setChosen] = useState(null)
  const [picked, setPicked] = useState([])
  const [issued, setIssued] = useState([])
  const [form, setForm] = useState({ enrollment_no: '', full_name: '' })
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = () =>
    Promise.all([api.candidates(), api.assessments()])
      .then(([c, a]) => {
        setCandidates(c)
        setAssessments(a)
        if (chosen === null && a.length) setChosen(a[0].id)
      })
      .catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  useEffect(() => {
    if (chosen) api.listCodes(chosen).then(setCodes).catch(() => setCodes([]))
  }, [chosen, issued])

  async function enrol() {
    setError(''); setNotice('')
    if (!form.enrollment_no.trim()) return setError('Enter an enrolment number.')
    try {
      await api.enrolCandidate({ enrollment_no: form.enrollment_no, full_name: form.full_name })
      setForm({ enrollment_no: '', full_name: '' })
      setNotice('Candidate enrolled.')
      load()
    } catch (e) { setError(e.message) }
  }

  async function generate() {
    setError(''); setNotice(''); setIssued([])
    if (!picked.length) return setError('Select at least one candidate.')
    try {
      const result = await api.issueCodes({ assessment_id: chosen, enrollment_numbers: picked })
      setIssued(result)
      setPicked([])
      setNotice(`${result.length} code${result.length === 1 ? '' : 's'} issued. Copy them now — they cannot be shown again.`)
    } catch (e) { setError(e.message) }
  }

  const statusOf = (enrollment) => {
    const record = codes.find((c) => c.enrollment_no === enrollment && !c.revoked)
    if (!record) return { label: 'no code', tone: '' }
    if (record.used_at) return { label: 'used', tone: 'tag-verdict' }
    return { label: 'issued', tone: 'tag-primary' }
  }

  return (
    <div className="stack" style={{ gap: '1.5rem' }}>
      <div>
        <span className="eyebrow">Examiner</span>
        <h1 style={{ marginTop: '.3rem' }}>Candidates and exam codes</h1>
        <p className="muted small" style={{ marginTop: '.4rem' }}>
          Candidates hold no standing password. Each sitting is opened by a single-use code
          tied to one paper. You can only issue codes for your own assessments.
        </p>
      </div>

      {error && <Banner tone="alert">{error}</Banner>}
      {notice && <Banner tone="verdict">{notice}</Banner>}

      {issued.length > 0 && (
        <section className="panel stack" style={{ padding: '1.25rem', gap: '.75rem', borderLeft: '3px solid var(--signal)' }}>
          <div className="spread">
            <h2>Issued codes</h2>
            <button
              className="btn-ghost"
              onClick={() => navigator.clipboard?.writeText(
                issued.map((i) => `${i.enrollment_no}\t${i.full_name}\t${i.access_code}`).join('\n')
              )}
            >
              Copy all
            </button>
          </div>
          <p className="small muted" style={{ margin: 0 }}>
            Shown once. Only hashes are stored, so these cannot be looked up later.
          </p>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              {issued.map((i) => (
                <tr key={i.enrollment_no} style={{ borderTop: '1px solid var(--rule-soft)' }}>
                  <td className="mono small" style={{ padding: '.45rem 0' }}>{i.enrollment_no}</td>
                  <td className="small" style={{ padding: '.45rem .75rem' }}>{i.full_name}</td>
                  <td className="mono" style={{ padding: '.45rem 0', fontWeight: 600, letterSpacing: '.06em', textAlign: 'right' }}>
                    {i.access_code}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <div className="grid-2">
        <section className="panel stack" style={{ padding: '1.25rem', gap: '.75rem' }}>
          <h2>Enrol a candidate</h2>
          <label className="stack" style={{ gap: '.3rem' }}>
            <span className="eyebrow">Enrolment number</span>
            <input className="mono" value={form.enrollment_no} placeholder="21BCS1045"
              onChange={(e) => setForm((f) => ({ ...f, enrollment_no: e.target.value.toUpperCase() }))} />
          </label>
          <label className="stack" style={{ gap: '.3rem' }}>
            <span className="eyebrow">Full name</span>
            <input value={form.full_name} onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))} />
          </label>
          <button className="btn-ghost" style={{ alignSelf: 'flex-start' }} onClick={enrol}>Enrol</button>
        </section>

        <section className="panel stack" style={{ padding: '1.25rem', gap: '.75rem' }}>
          <h2>Issue codes</h2>
          <label className="stack" style={{ gap: '.3rem' }}>
            <span className="eyebrow">For assessment</span>
            <select value={chosen ?? ''} onChange={(e) => setChosen(Number(e.target.value))}>
              {assessments.map((a) => (
                <option key={a.id} value={a.id}>{a.title}{a.is_published ? '' : ' (draft)'}</option>
              ))}
            </select>
          </label>
          <p className="small muted" style={{ margin: 0 }}>
            {picked.length} selected. Reissuing revokes any unused code for the same paper.
          </p>
          <button className="btn-primary" style={{ alignSelf: 'flex-start' }} onClick={generate} disabled={!picked.length}>
            Generate codes
          </button>
        </section>
      </div>

      <section className="stack" style={{ gap: '.5rem' }}>
        <div className="spread">
          <h2>Enrolled candidates</h2>
          <button className="btn-ghost" onClick={() => setPicked(picked.length ? [] : candidates.map((c) => c.enrollment_no))}>
            {picked.length ? 'Clear selection' : 'Select all'}
          </button>
        </div>
        {candidates.map((c) => {
          const on = picked.includes(c.enrollment_no)
          const status = statusOf(c.enrollment_no)
          return (
            <label key={c.id} className="panel spread" style={{
              padding: '.7rem 1rem', cursor: 'pointer',
              borderColor: on ? 'var(--primary)' : 'var(--rule)',
              background: on ? 'var(--primary-10)' : 'var(--panel)',
            }}>
              <div className="row" style={{ gap: '.75rem' }}>
                <input type="checkbox" checked={on} style={{ width: 'auto', margin: 0 }}
                  onChange={() => setPicked((p) => on ? p.filter((x) => x !== c.enrollment_no) : [...p, c.enrollment_no])} />
                <span className="mono" style={{ fontWeight: 600 }}>{c.enrollment_no}</span>
                <span className="small">{c.full_name}</span>
              </div>
              {status.label !== 'no code'
                ? <span className={`tag ${status.tone}`}>{status.label}</span>
                : <span className="small muted">no code for this paper</span>}
            </label>
          )
        })}
        {!candidates.length && (
          <div className="panel" style={{ padding: '2rem', textAlign: 'center' }}>
            <p className="muted" style={{ margin: 0 }}>No candidates enrolled yet.</p>
          </div>
        )}
      </section>
    </div>
  )
}

/** Inline notice. Colour lives in the stylesheet so both themes stay correct. */
function Banner({ tone, children }) {
  return <div className={`notice notice-${tone}`}>{children}</div>
}
