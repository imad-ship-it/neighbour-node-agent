/**
 * Query keys for notifications.
 *
 * Two keys and one crucial distinction: the COUNT is polled, the LIST is not.
 * The badge has to stay live on every page forever, so it asks a dedicated
 * endpoint that returns a single integer. The list is fetched only when someone
 * opens the dropdown — that is the whole reason the API separates them, and
 * re-uniting them here would undo it from the client side.
 */

export const UNREAD_COUNT_KEY = ['notifications', 'unread-count']
export const NOTIFICATIONS_KEY = ['notifications', 'list']

// Matches the conversation list's cadence. Anything faster is noise on a badge
// that shows a number most people glance at once a minute.
export const COUNT_POLL_MS = 10000
