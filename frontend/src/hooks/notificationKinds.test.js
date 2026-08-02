/**
 * Where a notification click lands.
 *
 * Worth testing without React because every case here is a destination, and a
 * wrong or dead one is only visible by clicking it — which, for the kinds
 * nothing currently writes, nobody ever will until a panel does.
 */

import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { iconFor, routeFor } from './notificationKinds.js'

describe('routeFor', () => {
  it('sends a message notification to its thread', () => {
    const route = routeFor({ type: 'new_message', conversation_id: 12 })

    assert.equal(route, '/messages/12')
  })

  it('sends a match notification to the listing, not a thread', () => {
    // The two kinds route to different places, which is the entire reason the
    // discriminator exists.
    const route = routeFor({ type: 'new_match', listing_id: 385 })

    assert.equal(route, '/listings/385')
  })

  it('returns null when the id the kind routes on is missing', () => {
    // `payload` is schemaless, so this is a real state rather than a defensive
    // hypothetical. The caller renders these as plain text: a row that looks
    // clickable and goes nowhere gets clicked during a demo.
    assert.equal(routeFor({ type: 'new_message', conversation_id: null }), null)
    assert.equal(routeFor({ type: 'new_match', listing_id: null }), null)
  })

  it('returns null for a kind this client has never heard of', () => {
    // bookmark_update is declared server-side and never written. A client
    // meeting it must not crash the whole dropdown.
    assert.equal(routeFor({ type: 'bookmark_update', listing_id: 1 }), null)
    assert.equal(routeFor({ type: 'something_invented_later' }), null)
  })
})

describe('iconFor', () => {
  it('gives each known kind its own icon', () => {
    // A message and a match are different events; identical icons would make
    // the dropdown unreadable at a glance.
    assert.equal(iconFor('new_message'), 'message')
    assert.equal(iconFor('new_match'), 'spark')
    assert.notEqual(iconFor('new_message'), iconFor('new_match'))
  })

  it('falls back to a generic bell rather than rendering nothing', () => {
    assert.equal(iconFor('bookmark_update'), 'bell')
    assert.equal(iconFor(undefined), 'bell')
  })
})
