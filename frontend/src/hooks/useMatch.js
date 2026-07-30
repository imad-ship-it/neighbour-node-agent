import { useMutation } from '@tanstack/react-query'
import client from '../api/client'

// Where the search happens from. Seeded listings cluster around Philadelphia, so
// real browser geolocation would put a user nowhere near them and every search
// would come back empty — which reads as a broken app, not an empty
// neighbourhood. Swap this for navigator.geolocation once there's real data.
export const DEFAULT_LAT = 40.0
export const DEFAULT_LNG = -75.0

async function postMatch({ text, lat = DEFAULT_LAT, lng = DEFAULT_LNG, fresh = false }) {
  const { data } = await client.post('/match/', { text, lat, lng, fresh })
  return data
}

/**
 * POST /api/match/ — a mutation, not a query.
 *
 * It's user-triggered, it costs a paid LLM call, and it writes server state (the
 * per-user MatchSession that makes the next search a refinement). useQuery would
 * refetch it on window focus and on remount, silently re-billing and mutating
 * that memory behind the user's back.
 */
export function useMatch() {
  return useMutation({ mutationFn: postMatch })
}
