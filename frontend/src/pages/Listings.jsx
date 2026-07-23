import { useListings } from '../hooks/useListings'
import ListingCard from '../components/ListingCard'

function Listings() {
  const { data, isLoading, isError } = useListings()

  if (isLoading) return <p>Loading...</p>
  if (isError) return <p>Failed to load listings.</p>

  return (
    <div>
      {data.map((listing) => (
        <ListingCard key={listing.id} listing={listing} />
      ))}
    </div>
  )
}

export default Listings
