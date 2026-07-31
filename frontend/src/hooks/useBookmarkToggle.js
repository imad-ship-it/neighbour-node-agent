import { useMutation, useQueryClient } from '@tanstack/react-query'
import client from '../api/client'

// Every cache surface a bookmark change can touch. Exported so the pages that
// read them can't drift from the keys this hook invalidates.
export const LISTINGS_KEY = ['listings']
export const BOOKMARKS_KEY = ['bookmarks']

/**
 * Add or remove, chosen by whether the listing already carries a bookmark id.
 *
 * The id comes from the server (ListingViewSet annotates `bookmark_id`), which
 * is what lets this be two plain REST calls instead of a toggle endpoint. A
 * toggle races itself: two quick clicks send two requests and the second can
 * flip the state back before the first response lands.
 */
async function toggleBookmark(listing) {
  if (listing.bookmark_id) {
    await client.delete(`/bookmarks/${listing.bookmark_id}/`)
    return { bookmarked: false }
  }
  const { data } = await client.post('/bookmarks/', { listing: listing.id })
  return { bookmarked: true, bookmarkId: data.id }
}

// The listings cache is a bare array today but Listings.jsx already tolerates a
// paginated envelope, so patch either shape rather than betting on one.
function patchListing(cached, listingId, patch) {
  if (!cached) return cached
  const rows = Array.isArray(cached) ? cached : cached.results
  if (!Array.isArray(rows)) return cached

  const next = rows.map((row) => (row.id === listingId ? { ...row, ...patch } : row))
  return Array.isArray(cached) ? next : { ...cached, results: next }
}

// On My Bookmarks the row should vanish, not go grey — un-bookmarking there is
// a removal, whereas on the listings page the same action just flips a flag.
function dropBookmarkFor(cached, listingId) {
  if (!Array.isArray(cached)) return cached
  return cached.filter((row) => row.listing?.id !== listingId)
}

/**
 * Bookmark/un-bookmark a listing, optimistically.
 *
 * Lives here rather than in ListingCard because the card renders on more than
 * one page. With the mutation inside the component, each mounted copy owns its
 * own state and two pages can disagree about whether the same listing is
 * saved — a bug that only appears when both are mounted at once. The card is
 * presentational and reads `is_bookmarked` straight off the server payload.
 *
 * Call it with the whole listing object: `toggle.mutate(listing)`.
 */
export function useBookmarkToggle() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: toggleBookmark,

    async onMutate(listing) {
      // An in-flight refetch that resolves after the optimistic write would
      // overwrite it with pre-click data, so stop them first.
      await Promise.all([
        queryClient.cancelQueries({ queryKey: LISTINGS_KEY }),
        queryClient.cancelQueries({ queryKey: BOOKMARKS_KEY }),
      ])

      const snapshot = {
        listings: queryClient.getQueryData(LISTINGS_KEY),
        bookmarks: queryClient.getQueryData(BOOKMARKS_KEY),
      }

      const removing = Boolean(listing.bookmark_id)

      queryClient.setQueryData(LISTINGS_KEY, (cached) =>
        patchListing(cached, listing.id, {
          is_bookmarked: !removing,
          // The real id only exists once the server answers. Null in the
          // meantime is honest, and it's safe: a second click before the
          // refetch lands re-POSTs, and create is idempotent by design, so it
          // returns the same row instead of erroring. (ListingCard also
          // disables the button while pending, so this is the backstop.)
          bookmark_id: null,
        })
      )

      if (removing) {
        queryClient.setQueryData(BOOKMARKS_KEY, (cached) =>
          dropBookmarkFor(cached, listing.id)
        )
      }

      return snapshot
    },

    onError(_error, _listing, snapshot) {
      if (!snapshot) return
      queryClient.setQueryData(LISTINGS_KEY, snapshot.listings)
      queryClient.setQueryData(BOOKMARKS_KEY, snapshot.bookmarks)
    },

    onSettled() {
      // Invalidate both rather than hand-patching each surface. The two caches
      // need different edits for the same action, and targeted cache surgery is
      // the version that breaks in a demo — a refetch is cheap and always right.
      queryClient.invalidateQueries({ queryKey: LISTINGS_KEY })
      queryClient.invalidateQueries({ queryKey: BOOKMARKS_KEY })
    },
  })
}
