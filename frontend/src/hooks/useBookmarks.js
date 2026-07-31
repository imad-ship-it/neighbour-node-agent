import { useQuery } from '@tanstack/react-query'
import client from '../api/client'
import { BOOKMARKS_KEY } from './useBookmarkToggle'

async function fetchBookmarks() {
  const { data } = await client.get('/bookmarks/')
  return data
}

/**
 * GET /api/bookmarks/ — the current user's saved listings.
 *
 * The key is imported rather than re-declared: useBookmarkToggle invalidates
 * BOOKMARKS_KEY after every change, and a second literal ['bookmarks'] written
 * here would work right up until one of them was edited.
 *
 * The endpoint 401s for anonymous callers, so pass `enabled: false` when there's
 * no user rather than firing a request that can only fail.
 */
export function useBookmarks({ enabled = true } = {}) {
  return useQuery({
    queryKey: BOOKMARKS_KEY,
    queryFn: fetchBookmarks,
    enabled,
  })
}
