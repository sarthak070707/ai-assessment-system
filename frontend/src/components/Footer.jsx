/**
 * Attribution footer.
 *
 * Edit BUILDERS below. `linkedin` is optional: a person without one is rendered
 * as plain text rather than a dead link, so a missing profile does not make the
 * credit look like an oversight.
 */
const BUILDERS = [
  { name: 'Sarthak Arya', linkedin: 'https://www.linkedin.com/in/sarthak-arya-059920303' },
  // Replace the link below with Satyam's real profile when he has one. Until
  // then it points at a name search, so it never lands on a stranger's page.
  { name: 'Satyam Verma', linkedin: 'https://www.linkedin.com/search/results/people/?keywords=Satyam+Verma' },
]

function LinkedInMark() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5ZM3 9h4v12H3V9Zm7 0h3.8v1.64h.05c.53-.95 1.83-1.95 3.76-1.95C21.4 8.69 22 11.3 22 14.2V21h-4v-6.03c0-1.44-.03-3.29-2.06-3.29-2.06 0-2.38 1.57-2.38 3.19V21h-4V9Z" />
    </svg>
  )
}

const chipStyle = {
  gap: '.5rem', padding: '.4rem .8rem',
  border: '1px solid var(--rule)', borderRadius: 999,
  textDecoration: 'none', color: 'var(--ink-2)', fontSize: '.85rem',
}

export default function Footer({ bordered = true }) {
  return (
    <footer style={{ borderTop: bordered ? '1px solid var(--rule)' : 'none', padding: '1.5rem' }}>
      <div
        className="row"
        style={{
          maxWidth: 960, margin: '0 auto', gap: '.6rem',
          flexWrap: 'wrap', justifyContent: 'center',
        }}
      >
        <span className="small muted" style={{ marginRight: '.2rem' }}>Built by</span>

        {BUILDERS.map((person) =>
          person.linkedin ? (
            <a
              key={person.name}
              href={person.linkedin}
              target="_blank"
              rel="noreferrer noopener"
              className="row builder-chip"
              style={chipStyle}
            >
              <LinkedInMark />
              {person.name}
            </a>
          ) : (
            <span key={person.name} className="row" style={chipStyle}>
              {person.name}
            </span>
          )
        )}
      </div>
    </footer>
  )
}
