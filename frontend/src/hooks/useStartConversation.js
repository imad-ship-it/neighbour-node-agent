import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import client from '../api/client'
import { CONVERSATIONS_KEY } from './messagingKeys'

async function startConversation(listingId) {
  const { data } = await client.post('/conversations/', { listing: listingId })
  return data
}

/**
 * "Message the lender" — open the thread for a listing, creating it if needed.
 *
 * One call does both because the endpoint is idempotent: a listing you've
 * already messaged about returns the existing thread with 200 rather than
 * erroring on the unique constraint. So the button never needs to know whether
 * a conversation exists, and a double-click can't produce two threads. That
 * property was decided back in the bookmarks work
 * (docs/api-conventions.md rule 4) and this is where it pays for itself.
 *
 * Navigating on success rather than making the caller do it keeps both entry
 * points — match results and listing cards — behaving identically.
 */
export function useStartConversation() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: startConversation,
    onSuccess: (conversation) => {
      // A brand-new thread should already be in the list when the user backs
      // out of it.
      queryClient.invalidateQueries({ queryKey: CONVERSATIONS_KEY })
      navigate(`/messages/${conversation.id}`)
    },
  })
}
