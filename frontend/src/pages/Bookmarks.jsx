import { Link } from 'react-router-dom'
import EmptyState from '../components/EmptyState'
import ListingCard from '../components/ListingCard'
import { useAuth } from '../context/AuthContext'
import { useBookmarks } from '../hooks/useBookmarks'

function Bookmarks() {
  const { user } = useAuth()
  // Skip the request entirely when logged out — the endpoint 401s, and an error
  // state would be the wrong story for "you're not signed in".
  const { data, isLoading, isError } = useBookmarks({ enabled: Boolean(user) })

  if (!user) {
    return (
      <div className="page">
        <header className="page-head">
          <h1>Saved items</h1>
        </header>
        <EmptyState title="Log in to see your saved items.">
          <Link to="/login">Log in</Link> or{' '}
          <Link to="/signup">create an account</Link>.
        </EmptyState>
      </div>
    )
  }

  if (isLoading) return <p className="state">Loading saved items…</p>
  if (isError) {
    return <p className="state state-error">Failed to load saved items.</p>
  }

  // Same tolerance as Listings: a bare array today, a paginated envelope later.
  const bookmarks = Array.isArray(data) ? data : (data?.results ?? [])

  return (
    <div className="page">
      <header className="page-head">
        <h1>Saved items</h1>
        <p>
          {bookmarks.length} item{bookmarks.length === 1 ? '' : 's'} saved
        </p>
      </header>

      {bookmarks.length === 0 ? (
        <EmptyState title="Nothing saved yet.">
          Tap the bookmark icon on any listing to keep it here.{' '}
          <Link to="/">Browse listings</Link>.
        </EmptyState>
      ) : (
        <div className="listing-grid">
          {bookmarks.map((bookmark) => (
            // The row is the bookmark; the card wants the listing. The API nests
            // it whole precisely so this page needs no second round-trip — and
            // the nested payload carries is_bookmarked/bookmark_id, so the card
            // draws a filled icon and can un-save without a lookup.
            <ListingCard key={bookmark.id} listing={bookmark.listing} />
          ))}
        </div>
      )}
    </div>
  )
}

export default Bookmarks
