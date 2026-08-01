// Where the access token lives between requests, and now across reloads.
//
// sessionStorage, deliberately, not localStorage. sessionStorage is scoped to a
// single TAB, which preserves the property the previous in-memory version had
// for free: two tabs are two independent sessions. That matters immediately —
// testing this app means being a lender in one tab and a borrower in another,
// and localStorage (shared across every tab on an origin) would have the second
// login silently replace the first.
//
// The security position, stated rather than assumed: any access token readable
// by JavaScript is exposed to XSS, and sessionStorage is no worse in that
// respect than the module variable it replaces — an injected script reads
// either. The production answer is a refresh token in an httpOnly cookie with a
// short-lived access token held in memory, which needs a refresh endpoint and a
// rotation flow this app doesn't have. Scoped out, not overlooked.
//
// Tab lifetime is a feature, not a limitation: closing the tab ends the
// session, so a shared machine doesn't keep one lying around.

const STORAGE_KEY = 'neighbournode.access'

let accessToken = null

function storage() {
  // Safari in private mode throws on access rather than returning null, and a
  // storage failure must never take the app down. Falling back to memory costs
  // reload-safety and nothing else.
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

export function setAccessToken(token) {
  accessToken = token

  const store = storage()
  if (!store) return
  try {
    if (token) store.setItem(STORAGE_KEY, token)
    else store.removeItem(STORAGE_KEY)
  } catch {
    // Quota, or a store that's disabled mid-session. The in-memory copy stands.
  }
}

export function getAccessToken() {
  if (accessToken) return accessToken

  // Cold read after a reload: the module variable is gone, but the tab isn't.
  const store = storage()
  if (!store) return null
  try {
    accessToken = store.getItem(STORAGE_KEY)
  } catch {
    accessToken = null
  }
  return accessToken
}
