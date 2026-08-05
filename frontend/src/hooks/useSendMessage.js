import { useMutation, useQueryClient } from '@tanstack/react-query'
import client from '../api/client'
import { useAuth } from '../context/useAuth'
import { mergeMessages } from './mergeMessages'
import { CONVERSATIONS_KEY, messagesKey } from './messagingKeys'

async function postMessage({ conversationId, body }) {
  const { data } = await client.post('/messages/', {
    conversation: conversationId,
    body,
  })
  return data
}

/**
 * Send a message, optimistically.
 *
 * Same cycle as useBookmarkToggle — cancel, snapshot, apply, roll back on
 * error, invalidate on settle — with one addition. A bookmark toggle flips a
 * flag that the server will report identically; a sent message becomes a NEW
 * row the poll will also deliver. Without a dedupe the optimistic copy and the
 * polled real one both render. mergeMessages owns that rule so the merge
 * behaves the same whether it was triggered by a poll or by this mutation.
 *
 * The conversation list is invalidated too: sending changes `last_message_body`
 * and moves nothing else, but the row would otherwise show stale preview text
 * until the 10s list poll caught up.
 */
export function useSendMessage(conversationId) {
  const queryClient = useQueryClient()
  const { user } = useAuth()

  return useMutation({
    mutationFn: (body) => postMessage({ conversationId, body }),

    async onMutate(body) {
      await queryClient.cancelQueries({ queryKey: messagesKey(conversationId) })
      const snapshot = queryClient.getQueryData(messagesKey(conversationId))

      const optimistic = {
        // A string id, deliberately: newestServerId() filters to integers, so a
        // pending message can never be mistaken for a real one and skew the
        // after_id cursor forward past messages that were never fetched.
        id: `pending-${Date.now()}`,
        optimistic: true,
        body,
        sender: { id: null, username: user?.username ?? '' },
        created_at: new Date().toISOString(),
      }

      queryClient.setQueryData(messagesKey(conversationId), (old = []) => [
        ...old,
        optimistic,
      ])

      return { snapshot }
    },

    onError(_error, _body, context) {
      if (context?.snapshot !== undefined) {
        queryClient.setQueryData(messagesKey(conversationId), context.snapshot)
      }
    },

    onSuccess(created) {
      // Fold the real row in immediately rather than waiting for the next poll,
      // so the pending copy resolves on send instead of up to 5s later.
      queryClient.setQueryData(messagesKey(conversationId), (old = []) =>
        mergeMessages(old, [created])
      )
    },

    onSettled() {
      queryClient.invalidateQueries({ queryKey: messagesKey(conversationId) })
      queryClient.invalidateQueries({ queryKey: CONVERSATIONS_KEY })
    },
  })
}
