import { useMutation, useQueryClient } from '@tanstack/react-query'
import client from '../api/client'
import Icon from './Icon'

function ListingCard({ listing }) {
  const queryClient = useQueryClient()

  const toggleBookmark = useMutation({
    mutationFn: () => client.post(`/listings/${listing.id}/bookmark/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['listings'] })
    },
  })

  return (
    <div className="listing-card">
      <button onClick={() => toggleBookmark.mutate()} disabled={toggleBookmark.isPending}>
        <Icon name={listing.is_bookmarked ? 'bookmark-filled' : 'bookmark-outline'} size="sm" />
      </button>
      <h3>{listing.title}</h3>
      <p>{listing.category} · {listing.condition}</p>
      <p>${listing.price}</p>
    </div>
  )
}

export default ListingCard
