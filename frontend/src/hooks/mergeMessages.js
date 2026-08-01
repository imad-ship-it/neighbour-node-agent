/**
 * Fold a freshly-fetched batch of messages into what we already hold.
 *
 * Its own module because it is pure and the semantics are fiddly enough to want
 * testing without standing up React, a query client and an HTTP layer.
 *
 * Two jobs. First, real messages are keyed by server id, so the same message
 * arriving twice — a poll overlapping a refetch — collapses to one row.
 *
 * Second, and this is the one that shows on screen: an optimistic message has
 * no server id, so when the real copy arrives by polling there is nothing to
 * match it against and BOTH render for a tick. Optimistic entries are dropped
 * once the server confirms a message with the same sender and body.
 *
 * That is a heuristic, stated plainly: send identical text twice in quick
 * succession and the second pending copy disappears a beat early. The correct
 * fix is a client-supplied id echoed back by the API, which is a backend change.
 */
export function mergeMessages(existing = [], incoming = []) {
  const byId = new Map()
  for (const message of existing) {
    if (!message.optimistic) byId.set(message.id, message)
  }
  for (const message of incoming) {
    byId.set(message.id, message)
  }

  const confirmed = [...byId.values()].sort((a, b) => a.id - b.id)
  const settled = new Set(confirmed.map(identity))

  const stillPending = existing.filter(
    (message) => message.optimistic && !settled.has(identity(message))
  )

  return [...confirmed, ...stillPending]
}

function identity(message) {
  return `${message.sender?.username ?? ''}|${message.body}`
}

/**
 * The highest server id held. Optimistic ids are strings by design, so they are
 * skipped — a pending message must never push the after_id cursor forward past
 * real messages that were never fetched.
 */
export function newestServerId(messages = []) {
  const ids = messages.map((m) => m.id).filter((id) => Number.isInteger(id))
  return ids.length ? Math.max(...ids) : null
}
