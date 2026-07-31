/**
 * "There's nothing here" — as an answer, not an error.
 *
 * Deliberately shares no styling with .state-error. An empty result is usually
 * the truth about the world (nothing saved yet, nothing nearby fits), and
 * dressing it in red makes a working app look broken. Errors get their own
 * treatment.
 *
 * `children` is the secondary line — keep the recovery action in it, because an
 * empty state without a next step just makes the user reach for the back button.
 */
function EmptyState({ title, children }) {
  return (
    <div className="state">
      <p>{title}</p>
      {children && <p className="state-sub">{children}</p>}
    </div>
  )
}

export default EmptyState
