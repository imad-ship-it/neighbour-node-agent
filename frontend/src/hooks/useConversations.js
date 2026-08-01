import { useQuery } from '@tanstack/react-query'
import client from '../api/client'
import { CONVERSATIONS_KEY, LIST_POLL_MS } from './messagingKeys'

async function fetchConversations() {
  const { data } = await client.get('/conversations/')
  return data
}

/**
 * GET /api/conversations/ — every thread you're in, newest first.
 *
 * Each row arrives with `unread_count`, `last_message_body` and
 * `last_message_at` already computed by the server, so the list renders without
 * a second request per row. That's the whole reason the backend annotates
 * rather than letting the client work it out.
 *
 * Polls, because a message can arrive without this tab doing anything.
 * `refetchIntervalInBackground: false` is TanStack's default, but it's set
 * explicitly here: leaving a poll running in a hidden tab is a real cost that
 * shouldn't depend on a default staying put across a version bump.
 *
 * The endpoint 401s when logged out, so pass `enabled: false` rather than
 * firing a request that can only fail.
 */
export function useConversations({ enabled = true } = {}) {
  return useQuery({
    queryKey: CONVERSATIONS_KEY,
    queryFn: fetchConversations,
    enabled,
    refetchInterval: LIST_POLL_MS,
    refetchIntervalInBackground: false,
  })
}

/**
 * GET /api/conversations/{id}/ — one thread's header detail.
 *
 * A separate request rather than finding the row in the cached list, because
 * opening /messages/5 directly must work when the list was never fetched. It
 * also 404s for a thread you aren't in, which is what turns a guessed URL into
 * a "not found" screen instead of a blank header.
 *
 * Doesn't poll: the title and the other participant don't change. The unread
 * count on this response goes stale, and nothing reads it — the badge lives on
 * the list.
 */
export function useConversation(conversationId, { enabled = true } = {}) {
  return useQuery({
    queryKey: [...CONVERSATIONS_KEY, conversationId],
    enabled: enabled && Boolean(conversationId),
    queryFn: async () => {
      const { data } = await client.get(`/conversations/${conversationId}/`)
      return data
    },
  })
}
