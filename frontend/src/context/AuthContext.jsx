import { createContext, useContext, useState } from 'react'
import client from '../api/client'
import { setAccessToken } from '../api/tokenStore'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(null)

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
    // If /me/ fails the token is still good, so fall back to the username we
    // already know rather than logging the user back out. The only thing lost
    // is the ability to recognise their own listings.
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

export function useAuth() {
  return useContext(AuthContext)
}
