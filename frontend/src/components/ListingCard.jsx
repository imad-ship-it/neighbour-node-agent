import { useMutation, useQueryClient } from '@tanstack/react-query'
import client from '../api/client'
import { useAuth } from '../context/AuthContext'
import Icon from './Icon'

// Backend values are snake_case enums ("sporting_goods", "like_new").
function label(value) {
  return value ? value.replace(/_/g, ' ') : ''
}

function ListingCard({ listing }) {
  const queryClient = useQueryClient()
  const { user } = useAuth()

  const toggleBookmark = useMutation({
    mutationFn: () => client.post(`/listings/${listing.id}/bookmark/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['listings'] })
    },
  })

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
            onClick={() => toggleBookmark.mutate()}
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
      </div>
    </article>
  )
}

export default ListingCard
