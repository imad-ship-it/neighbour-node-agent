import math

EARTH_RADIUS_KM = 6371


def haversine_distance(lat1, lon1, lat2, lon2):
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_KM * c


def search_listings_by_distance(lat, lng, radius_km, filters=None):
    """Return [(listing, distance_km), ...] within radius_km of (lat, lng),
    nearest-first.

    `filters` is an optional dict of ORM lookups, e.g.
    {"is_available": True, "category": "tools"}.

    A plain callable with no view/request dependency — the DRF geo-search view
    and the Day-5 MCP server both call this; neither reimplements it.
    """
    from apps.listings.models import Listing

    queryset = Listing.objects.all()
    if filters:
        queryset = queryset.filter(**filters)

    results = []
    for listing in queryset:
        distance = haversine_distance(lat, lng, listing.latitude, listing.longitude)
        if distance <= radius_km:
            results.append((listing, distance))

    results.sort(key=lambda pair: pair[1])
    return results
