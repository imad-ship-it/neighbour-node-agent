import { mediaUrl } from '../api/client'
import MatchExplanation from './MatchExplanation'
import MessageLenderButton from './MessageLenderButton'

// Backend values are snake_case enums ("sporting_goods", "like_new").
function label(value) {
  return value ? value.replace(/_/g, ' ') : ''
}

/**
 * One ranked result: the listing, why the agent picked it, and what's wrong with it.
 *
 * `match` is the agent's judgement (rank, score, explanation, factors, concerns);
 * `listing` is the server-resolved detail. They arrive as two arrays on the
 * response and are joined by the page.
 */
function MatchCard({ match, listing }) {
  // Defensive: the service filters hallucinated ids before building `listings`,
  // so a match without one shouldn't exist — but render nothing rather than a
  // card full of "undefined".
  if (!listing) return null

  const scorePct = Math.round(match.score * 100)

  return (
    <article className="match-card">
      <div className="match-rank" aria-label={`Rank ${match.rank}`}>
        {match.rank}
      </div>

      <div className="listing-media match-media">
        {listing.image ? (
          <img src={mediaUrl(listing.image)} alt="" />
        ) : (
          <span className="listing-placeholder">{label(listing.category)}</span>
        )}
      </div>

      <div className="match-body">
        <h3>{listing.title}</h3>

        <div className="listing-meta">
          <span className="tag">{label(listing.category)}</span>
          <span className="tag tag-muted">{label(listing.condition)}</span>
          <span className="tag tag-muted">{listing.distance_km} km away</span>
          {/* Raw 0-1 scores mean nothing to a person; a percentage at least
              reads as confidence, and showing it keeps the ranking honest. */}
          <span className="tag tag-muted">{scorePct}% match</span>
        </div>

        <p className="listing-price">
          ${listing.price}
          <span> / day</span>
        </p>

        <MatchExplanation text={match.explanation} />

        {match.matched_factors?.length > 0 && (
          <ul className="chips chips-good">
            {match.matched_factors.map((factor) => (
              <li key={factor} className="chip">
                {factor}
              </li>
            ))}
          </ul>
        )}

        {/* Where the trust flags finally reach a person. Everything upstream —
            the rules, the annotator seam, the ranking prompt — exists so this
            list can say "poor condition" before someone walks across town. */}
        {match.concerns?.length > 0 && (
          <ul className="chips chips-warn">
            {match.concerns.map((concern) => (
              <li key={concern} className="chip">
                {concern}
              </li>
            ))}
          </ul>
        )}

        {/* Where the agent's output becomes something you can act on. Everything
            upstream — retrieval, trust flags, ranking — exists so this button
            is worth pressing. */}
        <MessageLenderButton listingId={listing.id} lenderId={listing.lender_id} />
      </div>
    </article>
  )
}

export default MatchCard
