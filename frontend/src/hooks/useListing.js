import { useQuery } from '@tanstack/react-query'
import client from '../api/client'

/**
 * GET /api/listings/{id}/ — one listing.
 *
 * Exists because match notifications route to a listing, and until now nothing
 * in the app could show one on its own: cards render in grids and aren't
 * clickable. A notification pointing at a page that doesn't exist is worse than
 * no notification.
 *
 * Reads are public, so this works logged out — which matters, because the
 * detail page is the natural thing to share a link to.
 */
export function useListing(listingId) {
  return useQuery({
    queryKey: ['listings', listingId],
    enabled: Boolean(listingId),
    queryFn: async () => {
      const { data } = await client.get(`/listings/${listingId}/`)
      return data
    },
  })
}
