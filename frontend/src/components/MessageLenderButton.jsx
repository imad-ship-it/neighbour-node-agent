import { apiError } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useStartConversation } from '../hooks/useStartConversation'

/**
 * Opens (or creates) the thread for a listing.
 *
 * One component for both entry points — match results and listing cards — so
 * they can't drift. The match-result one is the important one: it's where the
 * ranked output stops being a list and becomes something you can act on.
 *
 * Hidden when logged out, and hidden on your own listings, because the server
 * rejects self-threads with a 400 and offering a button that can only fail is
 * worse than offering none.
 */
function MessageLenderButton({ listingId, lenderId }) {
  const { user } = useAuth()
  const start = useStartConversation()

  if (!user) return null

  // Fail closed on unknown identity.
  //
  // `user.id` is null when /auth/me/ failed, which means ownership cannot be
  // determined — NOT that this isn't mine. Showing the button then means a
  // lender can click it on their own listing and collect a 400 from the
  // self-conversation guard: correct server behaviour, terrible in front of an
  // audience. Hiding it costs one unavailable button in a state that shouldn't
  // occur; showing it costs a visible error in the state that does.
  if (user.id == null || user.id === lenderId) return null

  return (
    <>
      <button
        className="btn btn-sm"
        type="button"
        onClick={() => start.mutate(listingId)}
        disabled={start.isPending}
      >
        {start.isPending ? 'Opening…' : 'Message the lender'}
      </button>
      {start.isError && (
        <p className="form-error">
          {apiError(start.error, "Couldn't open that conversation.")}
        </p>
      )}
    </>
  )
}

export default MessageLenderButton
