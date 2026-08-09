import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { getUser, signOut } from '../api.js'

export default function Shell() {
  const user = getUser()
  const isStaff = user?.role === 'controller' || user?.role === 'examiner'
  const navigate = useNavigate()

  return (
    <div>
      <header style={{
        background: 'var(--panel)', borderBottom: '1px solid var(--rule)',
        padding: '0 1.5rem', position: 'sticky', top: 0, zIndex: 20,
      }}>
        <div className="spread" style={{ maxWidth: 1120, margin: '0 auto', height: 60 }}>
          <Link to="/" style={{ textDecoration: 'none', color: 'var(--ink)' }}>
            <span style={{ fontFamily: 'var(--display)', fontWeight: 700, letterSpacing: '-.02em' }}>
              {user?.role === 'controller' ? 'Exam office' : isStaff ? 'Workspace' : 'Assessment'}
            </span>
            <span className="mono muted" style={{ marginLeft: 8, fontSize: '.7rem' }}>v1.0</span>
          </Link>

          <nav className="row" style={{ gap: '1.25rem' }}>
            <Tab to="/">{isStaff ? 'Overview' : 'Assessments'}</Tab>
            {isStaff && <Tab to="/questions">Questions</Tab>}
            {isStaff && <Tab to="/assessments">Assessments</Tab>}
            {isStaff && <Tab to="/candidates">Candidates</Tab>}
            {isStaff && <Tab to="/review">Review queue</Tab>}
            {user?.role === 'controller' && <Tab to="/staff">Staff</Tab>}
            <span className="small muted" style={{ borderLeft: '1px solid var(--rule)', paddingLeft: '1.25rem' }}>
              {user?.enrollment_no
                ? <span className="mono">{user.enrollment_no}</span>
                : <>{user?.full_name}{user?.staff_id && <span className="mono"> · {user.staff_id}</span>}</>}
            </span>
            <button className="btn-ghost" onClick={() => { const staff = isStaff; signOut(); navigate(staff ? '/admin' : '/login') }}>
              Sign out
            </button>
          </nav>
        </div>
      </header>

      <main style={{ maxWidth: 1120, margin: '0 auto', padding: '2rem 1.5rem 4rem' }}>
        <Outlet />
      </main>
    </div>
  )
}

function Tab({ to, children }) {
  return (
    <NavLink
      to={to}
      style={({ isActive }) => ({
        textDecoration: 'none',
        fontSize: '.88rem',
        fontWeight: 500,
        color: isActive ? 'var(--primary)' : 'var(--ink-2)',
      })}
    >
      {children}
    </NavLink>
  )
}
