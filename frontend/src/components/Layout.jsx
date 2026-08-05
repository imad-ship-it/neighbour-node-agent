import { Link, NavLink } from 'react-router-dom'
import { useAuth } from '../context/useAuth'
import NotificationBell from './NotificationBell'

function Layout({ children }) {
  const { user, logout } = useAuth()

  return (
    <>
      <header className="site-header">
        <Link to="/" className="brand">
          Neighbour<span>Node</span>
        </Link>
        <nav className="site-nav">
          <NavLink to="/" end>
            Browse
          </NavLink>
          <NavLink to="/match">Find</NavLink>
          <NavLink to="/create">New listing</NavLink>
          {user ? (
            <>
              {/* Logged-out visitors have nothing saved, so the link would only
                  lead to a prompt. The route still handles that case for anyone
                  arriving by URL. */}
              <NavLink to="/saved">Saved</NavLink>
              <NavLink to="/messages">Messages</NavLink>
              <NotificationBell />
              <span className="who">{user.username}</span>
              <button className="btn btn-ghost" onClick={logout}>
                Log out
              </button>
            </>
          ) : (
            <>
              <NavLink to="/login">Log in</NavLink>
              <Link to="/signup" className="btn btn-sm">
                Sign up
              </Link>
            </>
          )}
        </nav>
      </header>
      <main className="site-main">{children}</main>
    </>
  )
}

export default Layout
