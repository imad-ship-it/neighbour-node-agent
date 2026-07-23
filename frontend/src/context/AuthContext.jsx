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
    setUser({ username })
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
