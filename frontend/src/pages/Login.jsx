import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { apiError } from '../api/client'
import Button from '../components/Button'

function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(username, password)
      navigate('/')
    } catch (err) {
      setError(apiError(err, 'Invalid username or password.'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <h2>Welcome back</h2>
      <label>
        Username
        <input value={username} onChange={(e) => setUsername(e.target.value)} />
      </label>
      <label>
        Password
        <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" />
      </label>
      {error && <p className="form-error">{error}</p>}
      {/* Disabled while in flight: the request is a round trip to the API, and
          without this the button stays live long enough to submit twice. */}
      <Button type="submit" disabled={submitting}>
        {submitting ? 'Logging in…' : 'Log in'}
      </Button>
      <p className="form-alt">
        No account? <Link to="/signup">Sign up</Link>
      </p>
    </form>
  )
}

export default Login
