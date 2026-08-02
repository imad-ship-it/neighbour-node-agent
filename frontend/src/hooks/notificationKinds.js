/**
 * How each notification kind renders and where it goes.
 *
 * Its own module rather than a constant inside NotificationBell, for the same
 * reason mergeMessages is: it is pure branching over data, it decides where a
 * click lands, and it can be tested without mounting React.
 *
 * Note what is NOT here: the sentence. The server renders `text`, so the
 * wording lives in one place instead of being duplicated in a second language.
 * This module owns only the icon and the destination.
 */

const KINDS = {
  new_message: {
    icon: 'message',
    route: (notification) =>
      notification.conversation_id
        ? `/messages/${notification.conversation_id}`
        : null,
  },
  new_match: {
    icon: 'spark',
    route: (notification) =>
      notification.listing_id ? `/listings/${notification.listing_id}` : null,
  },
}

// An unknown kind is a row written by code newer than this client. A generic
// bell and no destination beats a crash or a link that goes nowhere.
const FALLBACK = { icon: 'bell', route: () => null }

export function iconFor(type) {
  return (KINDS[type] ?? FALLBACK).icon
}

/**
 * Where clicking this notification should go, or null when there is nowhere.
 *
 * Null is a real answer, not a failure: `payload` is schemaless, so a row can
 * legitimately lack the id its kind routes on. The caller renders those as
 * plain text — a dropdown row that looks clickable and goes nowhere is the kind
 * of thing that gets clicked while demonstrating the product.
 */
export function routeFor(notification) {
  return (KINDS[notification.type] ?? FALLBACK).route(notification)
}
