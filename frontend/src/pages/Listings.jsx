import { useListings } from '../hooks/useListings'
import EmptyState from '../components/EmptyState'
import ListingCard from '../components/ListingCard'

function Listings() {
  const { data, isLoading, isError } = useListings()

  if (isLoading) return <p className="state">Loading listings…</p>
  if (isError) return <p className="state state-error">Failed to load listings.</p>

  // The API returns a plain array today; tolerate a paginated envelope too.
  const listings = Array.isArray(data) ? data : (data?.results ?? [])

  return (
    <div className="page">
      <header className="page-head">
        <h1>Borrow from your neighbours</h1>
        <p>
          {listings.length} item{listings.length === 1 ? '' : 's'} available nearby
        </p>
      </header>

      {listings.length === 0 ? (
        <EmptyState title="No listings yet.">
          Run <code>manage.py seed_data</code>, or add the first one.
        </EmptyState>
      ) : (
        <div className="listing-grid">
          {listings.map((listing) => (
            <ListingCard key={listing.id} listing={listing} />
          ))}
        </div>
      )}
    </div>
  )
}

export default Listings
