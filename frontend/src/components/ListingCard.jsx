function ListingCard({ listing }) {
  return (
    <div className="listing-card">
      <h3>{listing.title}</h3>
      <p>{listing.category} · {listing.condition}</p>
      <p>${listing.price}</p>
    </div>
  )
}

export default ListingCard
