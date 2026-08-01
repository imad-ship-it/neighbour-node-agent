const RELATIVE = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })

// Largest first — the loop takes the first unit the gap actually fills.
const UNITS = [
  ['year', 31536000],
  ['month', 2592000],
  ['week', 604800],
  ['day', 86400],
  ['hour', 3600],
  ['minute', 60],
]

/**
 * "2 hours ago", "yesterday", "just now".
 *
 * Intl rather than a date library: this is the only formatting the app needs,
 * and it's built into every browser we target. Anything under a minute reads as
 * "just now" instead of counting seconds, because a message list that reticks
 * every second draws the eye to the wrong thing.
 */
export function timeAgo(iso) {
  if (!iso) return ''
  const seconds = (new Date(iso).getTime() - Date.now()) / 1000

  for (const [unit, secondsInUnit] of UNITS) {
    if (Math.abs(seconds) >= secondsInUnit) {
      return RELATIVE.format(Math.round(seconds / secondsInUnit), unit)
    }
  }
  return 'just now'
}

/** "14:32" — for individual messages inside a thread. */
export function clockTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  })
}
