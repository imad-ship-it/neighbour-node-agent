import { useEffect, useLayoutEffect, useRef, useState } from 'react'
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
  const listRef = useRef(null)

  // Whether the reader is sitting at the bottom of the thread. Starts true so
  // the first batch of messages lands at the newest one.
  const pinnedToBottom = useRef(true)
  // Whether this thread has been scrolled into position at least once.
  const hasLanded = useRef(false)

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

  // Navigating between threads is a remount-less change of conversationId, so
  // the scroll state has to be reset by hand or thread B inherits thread A's.
  useEffect(() => {
    hasLanded.current = false
    pinnedToBottom.current = true
  }, [conversationId])

  /**
   * Three behaviours, not one.
   *
   *   opening a thread            -> jump to the newest message
   *   a message arrives, at bottom -> follow it down
   *   a message arrives, scrolled up -> DON'T MOVE
   *
   * The third is why this can't just scroll on every change: yanking someone
   * to the bottom while they're reading history is the most irritating thing a
   * chat UI can do, and it happens exactly when the conversation is liveliest.
   *
   * Sets scrollTop on the container rather than calling scrollIntoView on a
   * sentinel div. The sentinel is zero-height and sits after the last message,
   * so asking it to bring itself into view races the list's final height and
   * silently does nothing — which is why threads were opening at the top.
   *
   * useLayoutEffect, not useEffect: this runs before paint, so the thread is
   * already at the bottom on its first frame rather than visibly jumping.
   */
  useLayoutEffect(() => {
    const list = listRef.current
    if (!list || !newestId) return

    if (!hasLanded.current || pinnedToBottom.current) {
      list.scrollTop = list.scrollHeight
      hasLanded.current = true
    }
  }, [newestId])

  function handleScroll() {
    const list = listRef.current
    if (!list) return
    // A little slack: "near enough the bottom" counts as following along,
    // which keeps the behaviour stable against sub-pixel rounding and a
    // half-scrolled last message.
    const fromBottom = list.scrollHeight - list.scrollTop - list.clientHeight
    pinnedToBottom.current = fromBottom < 120
  }

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
        {/* Person first, listing second — a thread is WITH someone, ABOUT
            something, and that's the order you think in when you open it. The
            conversation list does the opposite on purpose: there the listing is
            what distinguishes two threads with the same lender. */}
        <span className="thread-head-text">
          <span className="thread-title">{other.username}</span>
          <span className="thread-preview">{listing.title}</span>
        </span>
      </header>

      <div className="message-list" ref={listRef} onScroll={handleScroll}>
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
