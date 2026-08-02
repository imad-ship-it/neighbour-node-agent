/**
 * The polling merge, tested with node:test — no framework, no React, no query
 * client, no HTTP.
 *
 * This function is the only place in the frontend where a bug is invisible by
 * inspection: an optimistic message carries no server id, so when the polled
 * copy arrives there is nothing to match it against and both render for a tick.
 * That is a one-frame flicker nobody reliably catches by clicking.
 *
 * Run with `npm test`.
 */

import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { mergeMessages, newestServerId } from './mergeMessages.js'

const from = (username, body, id) => ({
  id,
  body,
  sender: { username },
})

const pending = (username, body, id = 'pending-1') => ({
  ...from(username, body, id),
  optimistic: true,
})

describe('mergeMessages', () => {
  it('keeps server messages in id order', () => {
    const merged = mergeMessages([], [from('bob', 'second', 2), from('bob', 'first', 1)])

    assert.deepEqual(
      merged.map((m) => m.body),
      ['first', 'second']
    )
  })

  it('collapses the same message arriving twice', () => {
    // A poll overlapping a refetch delivers the same row on both.
    const merged = mergeMessages([from('bob', 'hello', 1)], [from('bob', 'hello', 1)])

    assert.equal(merged.length, 1)
  })

  it('drops an optimistic message once the server confirms it', () => {
    // The bug this whole module exists for: without the dedupe, "hello" renders
    // twice — once pending, once real.
    const merged = mergeMessages(
      [pending('alice', 'hello')],
      [from('alice', 'hello', 7)]
    )

    assert.equal(merged.length, 1)
    assert.equal(merged[0].id, 7, 'the surviving copy must be the SERVER one')
    assert.equal(merged[0].optimistic, undefined)
  })

  it('keeps an optimistic message the server has not confirmed yet', () => {
    const merged = mergeMessages([pending('alice', 'still sending')], [])

    assert.equal(merged.length, 1)
    assert.equal(merged[0].optimistic, true)
  })

  it('does not let someone else saying the same thing confirm my pending copy', () => {
    // The dedupe keys on sender AND body. Keying on body alone would make
    // "ok" from the other person silently swallow my unsent "ok".
    const merged = mergeMessages([pending('alice', 'ok')], [from('bob', 'ok', 3)])

    assert.equal(merged.length, 2)
    assert.ok(merged.some((m) => m.optimistic))
  })

  it('puts pending messages after confirmed ones', () => {
    const merged = mergeMessages(
      [pending('alice', 'newest')],
      [from('bob', 'older', 1)]
    )

    assert.deepEqual(
      merged.map((m) => m.body),
      ['older', 'newest']
    )
  })

  it('survives empty input on either side', () => {
    assert.deepEqual(mergeMessages(), [])
    assert.deepEqual(mergeMessages([], []), [])
  })
})

describe('newestServerId', () => {
  it('returns the highest server id', () => {
    assert.equal(newestServerId([from('a', 'x', 3), from('a', 'y', 9)]), 9)
  })

  it('ignores optimistic ids entirely', () => {
    // The important one. Optimistic ids are strings on purpose: if a pending
    // message could push the after_id cursor forward, the next poll would skip
    // real messages that were never fetched — and only for the person who just
    // sent something.
    const newest = newestServerId([from('a', 'x', 4), pending('a', 'y')])

    assert.equal(newest, 4)
  })

  it('returns null when there is nothing real to page from', () => {
    assert.equal(newestServerId([]), null)
    assert.equal(newestServerId([pending('a', 'x')]), null)
  })
})
