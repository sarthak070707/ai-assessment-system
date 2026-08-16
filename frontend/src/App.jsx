import { Navigate, Route, Routes } from 'react-router-dom'
import { getUser } from './api.js'
import Shell from './components/Shell.jsx'
import Landing from './pages/Landing.jsx'
import Login from './pages/Login.jsx'
import AdminLogin from './pages/AdminLogin.jsx'
import Candidates from './pages/Candidates.jsx'
import Staff from './pages/Staff.jsx'
import ImportQuestions from './pages/ImportQuestions.jsx'
import SetPassword from './pages/SetPassword.jsx'
import Dashboard from './pages/Dashboard.jsx'
import TakeTest from './pages/TakeTest.jsx'
import Result from './pages/Result.jsx'
import Review from './pages/Review.jsx'
import QuestionBank from './pages/QuestionBank.jsx'
import Assessments from './pages/Assessments.jsx'

const STAFF = ['controller', 'examiner']

function Protected({ children, staffOnly = false, controllerOnly = false }) {
  const user = getUser()
  const needsStaff = staffOnly || controllerOnly
  // Send people back to the door they came in by, not a shared one.
  if (!user) return <Navigate to={needsStaff ? '/admin' : '/login'} replace />
  // An account still on its temporary password goes nowhere else first.
  if (user.must_change_password) return <Navigate to="/set-password" replace />
  if (needsStaff && !STAFF.includes(user.role)) return <Navigate to="/" replace />
  if (controllerOnly && user.role !== 'controller') return <Navigate to="/" replace />
  return children
}

/** Bare '/' shows the portal chooser to visitors and the dashboard to anyone signed in. */
function Home() {
  const user = getUser()
  if (!user) return <Navigate to="/welcome" replace />
  if (user.must_change_password) return <Navigate to="/set-password" replace />
  return <Dashboard />
}

export default function App() {
  return (
    <Routes>
      {/* Front door for anyone not signed in; signed-in users go to their own
          dashboard instead, so the chooser never interrupts a working session. */}
      <Route path="/welcome" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/admin" element={<AdminLogin />} />
      <Route path="/set-password" element={<SetPassword />} />
      {/* The test screen sits outside the shell: no nav to click away to. */}
      <Route path="/test/:assessmentId" element={<Protected><TakeTest /></Protected>} />
      <Route element={<Shell />}>
        <Route path="/" element={<Home />} />
        <Route path="/result/:attemptId" element={<Protected><Result /></Protected>} />
        <Route path="/review" element={<Protected staffOnly><Review /></Protected>} />
        <Route path="/questions" element={<Protected staffOnly><QuestionBank /></Protected>} />
        <Route path="/questions/import" element={<Protected staffOnly><ImportQuestions /></Protected>} />
        <Route path="/assessments" element={<Protected staffOnly><Assessments /></Protected>} />
        <Route path="/candidates" element={<Protected staffOnly><Candidates /></Protected>} />
        <Route path="/staff" element={<Protected controllerOnly><Staff /></Protected>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
