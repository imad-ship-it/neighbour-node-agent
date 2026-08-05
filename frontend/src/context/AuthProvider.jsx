import { useEffect, useState } from 'react'
import client from '../api/client'
import { getAccessToken, setAccessToken } from '../api/tokenStore'
import { AuthContext } from './AuthContext'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  // Lazy initialiser rather than setting this from the effect below: the token
  // is already known synchronously at first render, so seeding state with it
  // avoids an extra render pass where context claims to be logged out while the
  // request interceptor is already sending a valid credential.
  const [token, setToken] = useState(() => getAccessToken())

  // Restore the session on boot, from the token rather than from a login event.
  //
  // Now that the token survives a reload in sessionStorage, this is the path
  // that runs on every refresh — and it's why identity must follow the TOKEN.
  // Loading it only on the login transition would leave a reloaded tab
  // authenticated with no user id, which nothing downstream could detect: a
  // lender would silently see "message the lender" on their own listings.
  useEffect(() => {
    if (!getAccessToken()) return

    let cancelled = false
    client
      .get('/auth/me/')
      .then(({ data }) => {
        if (!cancelled) setUser(data)
      })
      .catch(() => {
        // An expired or rejected token is a logged-out user, not a broken app.
        // Clearing it also stops every subsequent request retrying with a
        // credential the server has already refused.
        if (!cancelled) logout()
      })

    return () => {
      cancelled = true
    }
  }, [])

  async function login(username, password) {
    const { data } = await client.post('/auth/login/', { username, password })
    setToken(data.access)
    setAccessToken(data.access)

    // Fetch the profile rather than assembling it from the form. The login
    // response is a token pair and carries no identity, and the app needs the
    // user's ID — "is this listing mine?" compares against Listing.lender and
    // ListingSummary.lender_id, both of which are ids. A username can't answer
    // that question.
    //
    // The fallback keeps the session alive when /me/ fails, because the token
    // is still good. `id: null` then means "identity unknown", and every caller
    // must treat it as unknown rather than as "not me" — see
    // MessageLenderButton, which hides rather than guesses.
    try {
      const { data: profile } = await client.get('/auth/me/')
      setUser(profile)
    } catch {
      setUser({ id: null, username })
    }
  }

  async function register(username, email, password) {
    await client.post('/auth/register/', { username, email, password })
    return login(username, password)
  }

  function logout() {
    setToken(null)
    setAccessToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, token, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
