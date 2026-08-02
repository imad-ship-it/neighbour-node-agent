import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { iconFor, routeFor } from '../hooks/notificationKinds'
import {
  useMarkNotificationsRead,
  useNotifications,
  useUnreadCount,
} from '../hooks/useNotifications'
import { timeAgo } from '../utils/time'
import EmptyState from './EmptyState'
import Icon from './Icon'

function NotificationBell() {
  const { user } = useAuth()
  const signedIn = Boolean(user)

  const [open, setOpen] = useState(false)
  const containerRef = useRef(null)

  const { data: unread = 0 } = useUnreadCount({ enabled: signedIn })
  const { data: notifications = [], isLoading } = useNotifications({
    enabled: signedIn && open,
  })
  const { mutate: markRead } = useMarkNotificationsRead()

  // Mark what's on screen read, per the agreed semantics: opening the dropdown
  // clears what you were shown. Keyed on the ids so a second batch arriving
  // while the panel is open gets cleared too.
  const visibleUnreadIds = notifications
    .filter((n) => !n.is_read)
    .map((n) => n.id)
    .join(',')

  useEffect(() => {
    if (!open || !visibleUnreadIds) return
    markRead(visibleUnreadIds.split(',').map(Number))
  }, [open, visibleUnreadIds, markRead])

  // Click-away and Escape. A dropdown that only closes via its own button is
  // the kind of thing that traps someone mid-demo.
  useEffect(() => {
    if (!open) return

    function onPointerDown(event) {
      if (!containerRef.current?.contains(event.target)) setOpen(false)
    }
    function onKeyDown(event) {
      if (event.key === 'Escape') setOpen(false)
    }

    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  if (!signedIn) return null

  return (
    <div className="bell" ref={containerRef}>
      <button
        className="bell-button"
        onClick={() => setOpen((wasOpen) => !wasOpen)}
        aria-label={
          unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'
        }
        aria-expanded={open}
      >
        <Icon name="bell" size="sm" />
        {/* Hidden at zero: a badge showing "0" is noise pretending to be
            information. Capped at 9+ so the pill keeps its shape. */}
        {unread > 0 && (
          <span className="bell-badge">{unread > 9 ? '9+' : unread}</span>
        )}
      </button>

      {open && (
        <div className="bell-panel" role="menu">
          {isLoading ? (
            <p className="state">Loading…</p>
          ) : notifications.length === 0 ? (
            <EmptyState title="Nothing new.">
              Messages and matches for your listings show up here.
            </EmptyState>
          ) : (
            <ul className="bell-list">
              {notifications.map((notification) => {
                const href = routeFor(notification)

                const body = (
                  <>
                    <Icon name={iconFor(notification.type)} size="sm" />
                    <span className="bell-text">
                      <span>{notification.text}</span>
                      <span className="bell-time">
                        {timeAgo(notification.created_at)}
                      </span>
                    </span>
                  </>
                )

                return (
                  <li
                    key={notification.id}
                    className={notification.is_read ? '' : 'bell-unread'}
                  >
                    {/* A row with no destination renders as text, not as a link
                        that goes nowhere — the payload can legitimately lack an
                        id, and a dead link in a dropdown gets clicked. */}
                    {href ? (
                      <Link
                        to={href}
                        className="bell-row"
                        onClick={() => setOpen(false)}
                      >
                        {body}
                      </Link>
                    ) : (
                      <span className="bell-row">{body}</span>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

export default NotificationBell
