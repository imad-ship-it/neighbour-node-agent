import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { apiError } from '../api/client'
import Button from '../components/Button'

function Signup() {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const { register } = useAuth()
  const navigate = useNavigate()

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await register(username, email, password)
      navigate('/')
    } catch (err) {
      setError(apiError(err, 'Could not sign up. Please try again.'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <h2>Create an account</h2>
      <label>
        Username
        <input value={username} onChange={(e) => setUsername(e.target.value)} />
      </label>
      <label>
        Email
        <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" />
      </label>
      <label>
        Password
        <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" />
      </label>
      {error && <p className="form-error">{error}</p>}
      {/* Registration creates a user — a double submit is a duplicate-username
          error on the second attempt, which reads as a bug to the person doing it. */}
      <Button type="submit" disabled={submitting}>
        {submitting ? 'Creating account…' : 'Sign up'}
      </Button>
      <p className="form-alt">
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </form>
  )
}

export default Signup
