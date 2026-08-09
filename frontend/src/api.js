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

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: form ? new URLSearchParams(form) : body ? JSON.stringify(body) : undefined,
  })

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
    signOut()
    const staff = window.location.hash.startsWith('#/admin')
    window.location.hash = staff ? '#/admin' : '#/login'
    throw new Error('Session expired. Sign in again.')
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail.detail || 'Request failed. Try again.')
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
  updateQuestion: (id, payload) => request(`/questions/${id}`, { method: 'PUT', body: payload }),
  deleteQuestion: (id) => request(`/questions/${id}`, { method: 'DELETE' }),
  startAttempt: (id) => request(`/attempts/start/${id}`, { method: 'POST' }),
  submitAttempt: (id, answers) => request(`/attempts/${id}/submit`, { method: 'POST', body: { answers } }),
  logEvent: (id, event_type, detail = '') =>
    request(`/attempts/${id}/events`, { method: 'POST', body: { event_type, detail } }).catch(() => {}),
  myAttempts: () => request('/attempts/mine'),
  attempt: (id) => request(`/attempts/${id}`),
  analytics: (id) => request(`/analytics/attempt/${id}`),
  cohort: (id) => request(`/analytics/assessment/${id}`),
  reviewQueue: () => request('/attempts/review/queue'),
  applyReview: (answerId, score, feedback) =>
    request(`/attempts/review/${answerId}`, { method: 'POST', body: { score, feedback } }),
}
