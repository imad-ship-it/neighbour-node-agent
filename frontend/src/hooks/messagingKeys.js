/**
 * Query keys for messaging, in one place.
 *
 * useBookmarkToggle exports its two keys directly because there are exactly two
 * and they're constants. Messaging has a per-conversation key, so a hook that
 * only sends messages would otherwise have to import from the hook that lists
 * them purely to build a key — an import that says nothing about what the code
 * does. A key module keeps that dependency pointing at data rather than at
 * behaviour.
 *
 * Nothing here should ever be re-declared inline. A second literal
 * ['conversations'] works right up until one of them is edited, and the failure
 * is silent: a mutation invalidates a key nothing reads, so the screen simply
 * stops updating.
 */

export const CONVERSATIONS_KEY = ['conversations']

export const messagesKey = (conversationId) => ['messages', conversationId]

// The thread is the surface someone is actively watching, so it polls faster.
// The list only needs to notice a badge changing.
export const THREAD_POLL_MS = 5000
export const LIST_POLL_MS = 10000
