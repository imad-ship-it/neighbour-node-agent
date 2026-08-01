import { useQuery, useQueryClient } from '@tanstack/react-query'
import client from '../api/client'
import { mergeMessages, newestServerId } from './mergeMessages'
import { messagesKey, THREAD_POLL_MS } from './messagingKeys'

/**
 * GET /api/messages/?conversation=… — one thread, oldest first.
 *
 * Polls incrementally: each tick asks only for messages newer than the highest
 * id already held, then merges. A thread that has been open for a while
 * therefore costs a near-empty response every few seconds rather than
 * re-sending its whole history.
 *
 * The trade-off, stated: this only ever ADDS. An edited or deleted message
 * would never be noticed, because the poll never re-reads what it already
 * holds. Neither exists as a feature; both would need a different strategy —
 * a periodic full refetch, or a server-side change feed.
 *
 * `refetchIntervalInBackground: false` is TanStack's default, set explicitly
 * because a poll left running in a hidden tab is a real cost and shouldn't
 * depend on a default staying put across a version bump.
 */
export function useMessages(conversationId, { enabled = true } = {}) {
  const queryClient = useQueryClient()

  return useQuery({
    queryKey: messagesKey(conversationId),
    enabled: enabled && Boolean(conversationId),
    refetchInterval: THREAD_POLL_MS,
    refetchIntervalInBackground: false,
    queryFn: async () => {
      const existing = queryClient.getQueryData(messagesKey(conversationId)) ?? []

      const params = new URLSearchParams({ conversation: String(conversationId) })
      const after = newestServerId(existing)
      if (after !== null) params.set('after_id', String(after))

      const { data } = await client.get(`/messages/?${params.toString()}`)
      return mergeMessages(existing, data)
    },
  })
}
