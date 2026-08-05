import { useAuth } from '../context/useAuth'
import { useBookmarkToggle } from '../hooks/useBookmarkToggle'
import Icon from './Icon'
import MessageLenderButton from './MessageLenderButton'

// Backend values are snake_case enums ("sporting_goods", "like_new").
function label(value) {
  return value ? value.replace(/_/g, ' ') : ''
}

/**
 * One listing, presentationally. Renders on the listings page and on My
 * Bookmarks, so it holds no bookmark state of its own — `is_bookmarked` comes
 * annotated on the payload, and the mutation lives in useBookmarkToggle. Local
 * state here would let two mounted pages disagree about the same listing.
 */
function ListingCard({ listing }) {
  const { user } = useAuth()
  const toggleBookmark = useBookmarkToggle()

  return (
    <article className="listing-card">
      <div className="listing-media">
        {listing.image ? (
          <img src={listing.image} alt="" />
        ) : (
          <span className="listing-placeholder">{label(listing.category)}</span>
        )}
        {/* Bookmarking needs auth — hide it rather than fire a silent 401. */}
        {user && (
          <button
            className="bookmark"
            onClick={() => toggleBookmark.mutate(listing)}
            disabled={toggleBookmark.isPending}
            aria-label={listing.is_bookmarked ? 'Remove bookmark' : 'Bookmark'}
          >
            <Icon
              name={listing.is_bookmarked ? 'bookmark-filled' : 'bookmark-outline'}
              size="sm"
            />
          </button>
        )}
      </div>

      <div className="listing-body">
        <h3>{listing.title}</h3>
        <p className="listing-desc">{listing.description}</p>
        <div className="listing-meta">
          <span className="tag">{label(listing.category)}</span>
          <span className="tag tag-muted">{label(listing.condition)}</span>
          {!listing.is_available && <span className="tag tag-out">on loan</span>}
        </div>
        <p className="listing-price">
          ${listing.price}
          <span> / day</span>
        </p>

        <MessageLenderButton listingId={listing.id} lenderId={listing.lender} />
      </div>
    </article>
  )
}

export default ListingCard
