import { useState } from 'react'
import { Link } from 'react-router-dom'
import { apiError } from '../api/client'
import Button from '../components/Button'
import MatchCard from '../components/MatchCard'
import { useAuth } from '../context/useAuth'
import { DEFAULT_LAT, DEFAULT_LNG, useMatch } from '../hooks/useMatch'

const EXAMPLES = [
  'I need a cordless drill for the weekend, nothing over $50',
  'something to help me move furniture on saturday',
  'I need to cut through some metal pipes',
]

function Match() {
  const { user } = useAuth()
  const [text, setText] = useState('')
  const match = useMatch()
  const result = match.data

  function search(event, { fresh = false } = {}) {
    event?.preventDefault()
    const query = text.trim()
    if (!query) return
    match.mutate({ text: query, lat: DEFAULT_LAT, lng: DEFAULT_LNG, fresh })
  }

  // /api/match/ is IsAuthenticated. Say so up front rather than letting the
  // search fire and come back as a bare 401.
  if (!user) {
    return (
      <div className="page">
        <header className="page-head">
          <h1>Find something to borrow</h1>
        </header>
        <p className="state">
          <Link to="/login">Log in</Link> to search — matches are tied to your
          account so a follow-up search can build on the last one.
        </p>
      </div>
    )
  }

  return (
    <div className="page">
      <header className="page-head">
        <h1>Find something to borrow</h1>
        <p>Describe what you need in your own words — no need to name the item.</p>
      </header>

      <form className="match-form" onSubmit={search}>
        <input
          type="text"
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="e.g. I need to hang some shelves this weekend"
          aria-label="What do you need?"
        />
        <Button type="submit" disabled={match.isPending || !text.trim()}>
          {match.isPending ? 'Searching…' : 'Search'}
        </Button>
      </form>

      {!result && !match.isPending && !match.isError && (
        <ul className="match-examples">
          {EXAMPLES.map((example) => (
            <li key={example}>
              <button type="button" onClick={() => setText(example)}>
                {example}
              </button>
            </li>
          ))}
        </ul>
      )}

      {match.isPending && <p className="state">Asking the agent…</p>}

      {match.isError && (
        <p className="state state-error">
          {apiError(match.error, 'Search failed. Try again.')}
        </p>
      )}

      {result && (
        <>
          {/* Every one of these is a constraint the user didn't ask for. A
              search that quietly widened its radius, fell back to distance-only
              ordering, or inherited a previous query is lying by omission. */}
          <div className="match-notices">
            {result.refined && (
              <p className="notice">
                Building on your previous search.{' '}
                <button
                  type="button"
                  className="linklike"
                  onClick={(event) => search(event, { fresh: true })}
                >
                  Start over
                </button>
              </p>
            )}
            {result.widened && (
              <p className="notice">
                Nothing was in range, so we looked further out.
              </p>
            )}
            {result.degraded && (
              <p className="notice notice-warn">
                Ranking was unavailable — these are ordered by distance only.
              </p>
            )}
          </div>

          {result.matches.length === 0 ? (
            // Not an error state. A real neighbourhood often has nothing that
            // fits, and the agent is now told that returning nothing is the
            // correct answer rather than padding the list.
            <div className="state">
              <p>Nothing nearby fits that.</p>
              <p className="state-sub">
                {result.candidate_count} item
                {result.candidate_count === 1 ? '' : 's'} were considered.{' '}
                Try describing it differently, or{' '}
                <Link to="/">browse everything nearby</Link>.
              </p>
            </div>
          ) : (
            <>
              <p className="match-count">
                {result.matches.length} of {result.candidate_count} nearby items
                fit
              </p>
              <div className="match-list">
                {result.matches.map((m) => (
                  <MatchCard
                    key={m.listing_id}
                    match={m}
                    listing={result.listings.find((l) => l.id === m.listing_id)}
                  />
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}

export default Match
