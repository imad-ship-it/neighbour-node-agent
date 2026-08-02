import { Link, useParams } from 'react-router-dom'
import MessageLenderButton from '../components/MessageLenderButton'
import { useListing } from '../hooks/useListing'

// Backend values are snake_case enums ("sporting_goods", "like_new").
function label(value) {
  return value ? value.replace(/_/g, ' ') : ''
}

/**
 * One listing, in full.
 *
 * Deliberately minimal — it exists so match notifications have a real
 * destination. It reuses MessageLenderButton rather than growing its own copy,
 * so the "hidden on your own listings" rule holds here too without being
 * restated.
 */
function ListingDetail() {
  const { id } = useParams()
  const { data: listing, isLoading, isError } = useListing(Number(id))

  if (isLoading) return <p className="state">Loading listing…</p>
  if (isError) {
    return (
      <div className="page">
        <p className="state state-error">That listing doesn't exist.</p>
        <p className="state">
          <Link to="/">Browse listings</Link>
        </p>
      </div>
    )
  }

  return (
    <div className="page listing-detail">
      <p className="detail-back">
        <Link to="/">← Browse</Link>
      </p>

      <div className="detail-media">
        {listing.image ? (
          <img src={listing.image} alt="" />
        ) : (
          <span className="listing-placeholder">{label(listing.category)}</span>
        )}
      </div>

      <h1>{listing.title}</h1>

      <div className="listing-meta">
        <span className="tag">{label(listing.category)}</span>
        <span className="tag tag-muted">{label(listing.condition)}</span>
        {!listing.is_available && <span className="tag tag-out">on loan</span>}
      </div>

      <p className="listing-price">
        ${listing.price}
        <span> / day</span>
      </p>

      <p className="detail-description">{listing.description}</p>

      <MessageLenderButton listingId={listing.id} lenderId={listing.lender} />
    </div>
  )
}

export default ListingDetail
