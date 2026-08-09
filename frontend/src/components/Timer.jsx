import { useEffect, useState } from 'react'

/**
 * The exam clock, rendered twice: as a readout and as the hairline that drains
 * across the top of the viewport. Colour shifts at 25% and 10% remaining so
 * time pressure is visible peripherally, without the candidate watching digits.
 */
export default function Timer({ totalSeconds, onExpire }) {
  const [left, setLeft] = useState(totalSeconds)

  useEffect(() => {
    if (left <= 0) { onExpire(); return }
    const id = setTimeout(() => setLeft((s) => s - 1), 1000)
    return () => clearTimeout(id)
  }, [left, onExpire])

  const fraction = Math.max(0, left / totalSeconds)
  const state = fraction <= 0.1 ? 'critical' : fraction <= 0.25 ? 'warn' : ''
  const mm = String(Math.floor(Math.max(0, left) / 60)).padStart(2, '0')
  const ss = String(Math.max(0, left) % 60).padStart(2, '0')

  return (
    <>
      <div className={`hairline ${state}`} aria-hidden="true">
        <i style={{ width: `${fraction * 100}%` }} />
      </div>
      <div className="stack" style={{ alignItems: 'flex-end' }}>
        <span className="eyebrow">Time left</span>
        <span
          className="mono"
          role="timer"
          aria-live={state === 'critical' ? 'assertive' : 'off'}
          style={{
            fontSize: '1.45rem', fontWeight: 600, lineHeight: 1.1,
            color: state === 'critical' ? 'var(--alert)' : state === 'warn' ? 'var(--signal)' : 'var(--ink)',
          }}
        >
          {mm}:{ss}
        </span>
      </div>
    </>
  )
}
