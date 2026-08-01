import { Link } from 'react-router-dom'
import EmptyState from '../components/EmptyState'
import { useAuth } from '../context/AuthContext'
import { useConversations } from '../hooks/useConversations'
import { timeAgo } from '../utils/time'

function Conversations() {
  const { user } = useAuth()
  // Skip the request when logged out — the endpoint 401s, and an error state
  // tells the wrong story for "you're not signed in".
  const { data, isLoading, isError } = useConversations({ enabled: Boolean(user) })

  if (!user) {
    return (
      <div className="page">
        <header className="page-head">
          <h1>Messages</h1>
        </header>
        <EmptyState title="Log in to see your messages.">
          <Link to="/login">Log in</Link> or{' '}
          <Link to="/signup">create an account</Link>.
        </EmptyState>
      </div>
    )
  }

  if (isLoading) return <p className="state">Loading messages…</p>
  if (isError) return <p className="state state-error">Failed to load messages.</p>

  // Same tolerance as the other lists: a bare array today, an envelope later.
  const conversations = Array.isArray(data) ? data : (data?.results ?? [])
  const unread = conversations.reduce((sum, row) => sum + (row.unread_count || 0), 0)

  return (
    <div className="page">
      <header className="page-head">
        <h1>Messages</h1>
        <p>
          {conversations.length} conversation
          {conversations.length === 1 ? '' : 's'}
          {unread > 0 && ` · ${unread} unread`}
        </p>
      </header>

      {conversations.length === 0 ? (
        <EmptyState title="No messages yet.">
          Find something you'd like to borrow and message the lender.{' '}
          <Link to="/">Browse listings</Link>.
        </EmptyState>
      ) : (
        <ul className="thread-list">
          {conversations.map((conversation) => (
            <li key={conversation.id}>
              <Link to={`/messages/${conversation.id}`} className="thread-row">
                <span className="thread-media">
                  {conversation.listing.image ? (
                    <img src={conversation.listing.image} alt="" />
                  ) : (
                    <span className="thread-placeholder" aria-hidden="true" />
                  )}
                </span>

                <span className="thread-body">
                  <span className="thread-title">{conversation.listing.title}</span>
                  <span className="thread-preview">
                    <b>{conversation.other_participant.username}</b>
                    {conversation.last_message_body
                      ? ` · ${conversation.last_message_body}`
                      : ' · no messages yet'}
                  </span>
                </span>

                <span className="thread-meta">
                  <span className="thread-time">
                    {timeAgo(conversation.last_message_at)}
                  </span>
                  {conversation.unread_count > 0 && (
                    <span
                      className="thread-badge"
                      aria-label={`${conversation.unread_count} unread`}
                    >
                      {conversation.unread_count}
                    </span>
                  )}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default Conversations
