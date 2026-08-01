import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useConversation } from '../hooks/useConversations'
import { useMarkRead } from '../hooks/useMarkRead'
import { useMessages } from '../hooks/useMessages'
import { useSendMessage } from '../hooks/useSendMessage'
import { clockTime } from '../utils/time'

function Thread() {
  const { id } = useParams()
  const conversationId = Number(id)
  const { user } = useAuth()
  const signedIn = Boolean(user)

  const conversation = useConversation(conversationId, { enabled: signedIn })
  const { data: messages = [], isLoading } = useMessages(conversationId, {
    enabled: signedIn,
  })
  const send = useSendMessage(conversationId)
  const { mutate: markRead } = useMarkRead()

  const [draft, setDraft] = useState('')
  const endOfThread = useRef(null)

  // Newest id rather than length: length is unchanged when an optimistic
  // message is swapped for its real twin, so the two effects below would miss
  // the moment a send actually lands.
  const newestId = messages.length ? messages[messages.length - 1].id : null

  // Mark read on open, and again whenever something new arrives while the
  // thread is on screen — otherwise reading a live conversation still leaves
  // its badge lit. Safe to re-run: the endpoint is idempotent, and it
  // invalidates the conversation list, never the messages, so it can't loop.
  useEffect(() => {
    if (signedIn && conversationId) markRead(conversationId)
  }, [signedIn, conversationId, newestId, markRead])

  useEffect(() => {
    endOfThread.current?.scrollIntoView({ block: 'end' })
  }, [newestId])

  function handleSubmit(event) {
    event.preventDefault()
    const body = draft.trim()
    if (!body || send.isPending) return
    // Cleared before the request resolves — the optimistic message is already
    // on screen, so leaving the text in the box would read as "not sent".
    setDraft('')
    send.mutate(body)
  }

  if (!signedIn) {
    return (
      <div className="page">
        <p className="state">
          <Link to="/login">Log in</Link> to read your messages.
        </p>
      </div>
    )
  }

  if (conversation.isLoading) return <p className="state">Loading conversation…</p>

  if (conversation.isError) {
    // Scoping means a thread you aren't in is indistinguishable from one that
    // doesn't exist. Say that, rather than implying the app broke.
    return (
      <div className="page">
        <p className="state state-error">
          That conversation doesn't exist, or isn't yours.
        </p>
        <p className="state">
          <Link to="/messages">Back to messages</Link>
        </p>
      </div>
    )
  }

  const { listing, other_participant: other } = conversation.data

  return (
    <div className="page thread-view">
      <header className="thread-head">
        <Link to="/messages" className="thread-back" aria-label="Back to messages">
          ←
        </Link>
        {listing.image && <img src={listing.image} alt="" />}
        <span className="thread-head-text">
          <span className="thread-title">{listing.title}</span>
          <span className="thread-preview">with {other.username}</span>
        </span>
      </header>

      <div className="message-list">
        {isLoading ? (
          <p className="state">Loading messages…</p>
        ) : messages.length === 0 ? (
          <p className="state">
            No messages yet — say hello.
          </p>
        ) : (
          messages.map((message) => {
            const mine = message.sender.username === user.username
            return (
              <article
                key={message.id}
                className={`message${mine ? ' message-mine' : ''}${
                  message.optimistic ? ' message-pending' : ''
                }`}
              >
                <p className="message-body">{message.body}</p>
                <span className="message-time">
                  {message.optimistic ? 'sending…' : clockTime(message.created_at)}
                </span>
              </article>
            )
          })
        )}
        <div ref={endOfThread} />
      </div>

      {send.isError && (
        <p className="state state-error">
          That message didn't send. Try again.
        </p>
      )}

      <form className="message-form" onSubmit={handleSubmit}>
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={`Message ${other.username}…`}
          aria-label="Message"
        />
        <button className="btn" type="submit" disabled={!draft.trim()}>
          Send
        </button>
      </form>
    </div>
  )
}

export default Thread
