import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import client from '../api/client'
import {
  COUNT_POLL_MS,
  NOTIFICATIONS_KEY,
  UNREAD_COUNT_KEY,
} from './notificationKeys'

/**
 * GET /api/notifications/unread_count/ — the badge.
 *
 * Polls forever, on every page, so it must stay cheap: the endpoint returns
 * `{"unread": n}` and nothing else. Deliberately NOT derived from the list —
 * that would drag twenty serialized rows across the wire every ten seconds to
 * render one digit.
 *
 * `refetchIntervalInBackground: false` is the default, set explicitly because a
 * poll running in a hidden tab is a real cost that shouldn't depend on a
 * default surviving a version bump.
 */
export function useUnreadCount({ enabled = true } = {}) {
  return useQuery({
    queryKey: UNREAD_COUNT_KEY,
    enabled,
    refetchInterval: COUNT_POLL_MS,
    refetchIntervalInBackground: false,
    queryFn: async () => {
      const { data } = await client.get('/notifications/unread_count/')
      return data.unread
    },
  })
}

/**
 * GET /api/notifications/ — the dropdown's rows.
 *
 * On-demand only: `enabled` is the dropdown's open state, so nothing is fetched
 * until someone actually looks. The count is the live thing; the list is not.
 *
 * The response is paginated (uniquely in this API), so the results array is
 * unwrapped here rather than in every component that renders it.
 */
export function useNotifications({ enabled = false } = {}) {
  return useQuery({
    queryKey: NOTIFICATIONS_KEY,
    enabled,
    queryFn: async () => {
      const { data } = await client.get('/notifications/')
      return Array.isArray(data) ? data : (data?.results ?? [])
    },
  })
}

/**
 * POST /api/notifications/mark_read/ — clear what the user just saw.
 *
 * Takes the ids currently rendered, per the agreed semantics: opening the
 * dropdown marks the visible rows read. The server can't guess which those
 * were, so the client sends them.
 *
 * The response carries the fresh unread count, which is written straight into
 * the badge's cache. That's what makes the badge clear the moment the dropdown
 * opens rather than up to ten seconds later — without it the number would sit
 * there stale until the next poll tick, which reads as a broken button.
 */
export function useMarkNotificationsRead() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (ids) => {
      const { data } = await client.post('/notifications/mark_read/', { ids })
      return data
    },
    onSuccess: (data) => {
      queryClient.setQueryData(UNREAD_COUNT_KEY, data.unread)
      // The rows themselves are now read; refetch so reopening the dropdown
      // doesn't show them as unread.
      queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY })
    },
  })
}
