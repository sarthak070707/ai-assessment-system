import { useEffect, useRef } from 'react'
import { api } from '../api.js'

/**
 * Browser-side integrity signals. Each event is reported to the server, which
 * owns the count - the client is never trusted to keep the tally.
 *
 * Detects: leaving the tab, window blur, exiting full screen, and copy/paste
 * into the answer area. Deliberately does not block the candidate; it records,
 * and the examiner decides what the pattern means.
 */
export default function useProctor(attemptId, { enabled = true, onFlag, questionId } = {}) {
  const lastFlag = useRef(0)
  // Held in a ref because the listeners are registered once; reading the prop
  // directly would capture whichever question was on screen at mount and
  // attribute every later event to it.
  const currentQuestion = useRef(questionId)
  currentQuestion.current = questionId

  useEffect(() => {
    if (!enabled || !attemptId) return

    const report = (type, detail = '') => {
      const now = Date.now()
      if (now - lastFlag.current < 800) return // collapse duplicate blur/visibility pairs
      lastFlag.current = now
      onFlag?.(type)
      api.logEvent(attemptId, type, detail, currentQuestion.current)
    }

    const onVisibility = () => { if (document.hidden) report('tab_switch', 'Tab hidden') }
    const onBlur = () => report('window_blur', 'Window lost focus')
    const onFullscreen = () => {
      if (!document.fullscreenElement) report('fullscreen_exit', 'Left full screen')
    }
    const onPaste = (e) => {
      if (e.target?.dataset?.answer) report('paste', `${String(e.clipboardData?.getData('text') || '').length} chars`)
    }

    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('blur', onBlur)
    document.addEventListener('fullscreenchange', onFullscreen)
    document.addEventListener('paste', onPaste)
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('blur', onBlur)
      document.removeEventListener('fullscreenchange', onFullscreen)
      document.removeEventListener('paste', onPaste)
    }
  }, [attemptId, enabled, onFlag])
}
