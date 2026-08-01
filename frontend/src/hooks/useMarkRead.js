import { useMutation, useQueryClient } from '@tanstack/react-query'
import client from '../api/client'
import { CONVERSATIONS_KEY } from './messagingKeys'

/**
 * POST /api/conversations/{id}/read/ — mark a thread read up to now.
 *
 * Called on opening a thread, not on a button. The server decides which of the
 * two read-tracking columns to stamp, because that depends on whether you're
 * the initiator or the listing's lender — a distinction the client has no
 * business knowing.
 *
 * Invalidating the conversation list is the point of the mutation as far as the
 * UI is concerned: the unread badge lives on a list row, not in the thread, so
 * without this the badge stays lit behind you while you read.
 *
 * Deliberately no optimistic update. The response carries a recomputed
 * `unread_count`, and being briefly wrong about a badge is not worth the
 * rollback path — unlike a sent message, nobody is watching this happen.
 */
export function useMarkRead() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (conversationId) =>
      client.post(`/conversations/${conversationId}/read/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CONVERSATIONS_KEY })
    },
  })
}
