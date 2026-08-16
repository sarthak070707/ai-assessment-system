const BASE = '/api'

export function getToken() { return localStorage.getItem('token') }
export function getUser() {
  const raw = localStorage.getItem('user')
  return raw ? JSON.parse(raw) : null
}
export function signOut() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
}

async function request(path, { method = 'GET', body, form } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body) headers['Content-Type'] = 'application/json'

  let res
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: form ? new URLSearchParams(form) : body ? JSON.stringify(body) : undefined,
    })
  } catch {
    // fetch only rejects on a network-level failure, which in local development
    // means one thing: the API server is not running.
    throw new Error('Cannot reach the server. Is the backend running on port 8000?')
  }

  // 428 means a password change is outstanding; the app routes there rather
  // than treating it as a failed request.
  if (res.status === 428) {
    window.location.hash = '#/set-password'
    throw new Error('Set a new password before continuing.')
  }
  // A 401 from a sign-in attempt means the credentials were wrong, not that a
  // session lapsed. Treating the two alike discards the server's real message
  // and tells someone their session expired when they never had one.
  const isSignIn = path.startsWith('/auth/login') || path.startsWith('/auth/exam')
  if (res.status === 401 && !isSignIn) {
    // Read the role before signOut clears it. Guessing from the URL only matched
    // '#/admin' itself, so a session lapsing on '#/questions' sent an examiner
    // to the candidate portal.
    const role = getUser()?.role
    const wasStaff = role === 'controller' || role === 'examiner'
    signOut()
    window.location.hash = wasStaff ? '#/admin' : '#/login'
    throw new Error('Session expired. Sign in again.')
  }
  if (!res.ok) {
    const payload = await res.json().catch(() => null)

    // A non-JSON error body means the request never reached the API - the dev
    // proxy answered instead, because nothing was listening behind it.
    if (payload === null) {
      throw new Error(
        res.status >= 500
          ? 'Cannot reach the server. Is the backend running on port 8000?'
          : `Request failed (${res.status}).`
      )
    }

    // FastAPI returns a list of field errors for validation failures; the plain
    // string form is used everywhere else.
    const detail = payload.detail
    if (Array.isArray(detail)) {
      const first = detail[0]
      throw new Error(first?.msg ? `${first.msg}${first.loc ? ` (${first.loc.at(-1)})` : ''}` : 'Check the values you entered.')
    }
    throw new Error(detail || `Request failed (${res.status}).`)
  }
  return res.status === 204 ? null : res.json()
}

export const api = {
  staffLogin: async (email, password) => {
    const data = await request('/auth/login', {
      method: 'POST',
      form: { username: email, password },
    })
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('user', JSON.stringify(data.user))
    return data.user
  },
  examLogin: async (enrollment_no, access_code) => {
    const data = await request('/auth/exam', {
      method: 'POST',
      body: { enrollment_no, access_code },
    })
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('user', JSON.stringify(data.user))
    return data.user
  },

  staff: () => request('/staff'),
  createStaff: (payload) => request('/staff', { method: 'POST', body: payload }),
  updateStaff: (id, payload) => request(`/staff/${id}`, { method: 'PUT', body: payload }),
  resetStaffPassword: (id) => request(`/staff/${id}/reset`, { method: 'POST' }),
  toggleStaffActive: (id) => request(`/staff/${id}/deactivate`, { method: 'POST' }),
  changePassword: (current_password, new_password) =>
    request('/staff/change-password', { method: 'POST', body: { current_password, new_password } }),

  candidates: () => request('/candidates'),
  enrolCandidate: (payload) => request('/candidates', { method: 'POST', body: payload }),
  issueCodes: (payload) => request('/candidates/codes', { method: 'POST', body: payload }),
  listCodes: (assessmentId) => request(`/candidates/codes/${assessmentId}`),
  revokeCode: (id) => request(`/candidates/codes/${id}/revoke`, { method: 'POST' }),
  register: (payload) => request('/auth/register', { method: 'POST', body: payload }),
  assessments: () => request('/assessments'),
  createAssessment: (payload) => request('/assessments', { method: 'POST', body: payload }),
  updateAssessment: (id, payload) => request(`/assessments/${id}`, { method: 'PUT', body: payload }),
  togglePublish: (id) => request(`/assessments/${id}/publish`, { method: 'POST' }),
  deleteAssessment: (id) => request(`/assessments/${id}`, { method: 'DELETE' }),

  questions: () => request('/questions'),
  createQuestion: (payload) => request('/questions', { method: 'POST', body: payload }),
  importText: (text, default_marks) =>
    request('/questions/import/text', { method: 'POST', body: { text, default_marks } }),
  importFile: async (file, defaultMarks) => {
    const data = new FormData()
    data.append('file', file)
    const res = await fetch(`/api/questions/import/file?default_marks=${defaultMarks}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${getToken()}` },
      body: data,   // no Content-Type: the browser sets the multipart boundary
    })
    if (!res.ok) {
      const payload = await res.json().catch(() => null)
      throw new Error(payload?.detail || `Could not read that file (${res.status}).`)
    }
    return res.json()
  },
  importCommit: (skill, questions) =>
    request('/questions/import/commit', { method: 'POST', body: { skill, questions } }),
  updateQuestion: (id, payload) => request(`/questions/${id}`, { method: 'PUT', body: payload }),
  deleteQuestion: (id) => request(`/questions/${id}`, { method: 'DELETE' }),
  startAttempt: (id) => request(`/attempts/start/${id}`, { method: 'POST' }),
  saveDraft: (id, answers) => request(`/attempts/${id}/draft`, { method: 'PUT', body: { answers } }),
  submitAttempt: (id, answers) => request(`/attempts/${id}/submit`, { method: 'POST', body: { answers } }),
  logEvent: (id, event_type, detail = '', question_id = null) =>
    request(`/attempts/${id}/events`, {
      method: 'POST', body: { event_type, detail, question_id },
    }).catch(() => {}),
  myAttempts: () => request('/attempts/mine'),
  attempt: (id) => request(`/attempts/${id}`),
  analytics: (id) => request(`/analytics/attempt/${id}`),
  cohort: (id) => request(`/analytics/assessment/${id}`),
  reviewQueue: () => request('/attempts/review/queue'),
  applyReview: (answerId, score, feedback) =>
    request(`/attempts/review/${answerId}`, { method: 'POST', body: { score, feedback } }),
}
