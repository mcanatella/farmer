import numpy as np
from typing import Any

import pandas as pd


def calculate_levels_from_candles(
    candles, min_separation, price_tolerance, top_n
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Identify support and resistance levels from historical candle data.
    A level is considered valid if it is an isolated high/low compared to surrounding candles.
    Levels within `price_tolerance` are clustered together.
    Returns the top N support and resistance levels based on frequency and volume.
    """
    # Convert the raw candle data (list of dicts) into a DataFrame
    df = pd.DataFrame(candles)
    df["t"] = pd.to_datetime(df["t"])
    df.set_index("t", inplace=True)

    support_candidates = []
    resistance_candidates = []
    for i in range(min_separation, len(df) - min_separation):
        row = df.iloc[i]
        ts = df.index[i]
        low = row["l"]
        high = row["h"]
        volume = row["v"]

        # Check for isolated low; this low must be lower than lows of surrounding candles
        is_isolated_low = all(
            low < df.iloc[i - j]["l"] and low < df.iloc[i + j]["l"]
            for j in range(1, min_separation + 1)
        )

        if is_isolated_low:
            support_candidates.append((low, volume, ts))

        # Check for isolated high; this high must be higher than highs of surrounding candles
        is_isolated_high = all(
            high > df.iloc[i - j]["h"] and high > df.iloc[i + j]["h"]
            for j in range(1, min_separation + 1)
        )

        if is_isolated_high:
            resistance_candidates.append((high, volume, ts))

    # Return top support and resistance levels
    top_support = _cluster_levels(support_candidates, price_tolerance)[:top_n]
    top_resistance = _cluster_levels(resistance_candidates, price_tolerance)[:top_n]

    return top_support, top_resistance


def _cluster_levels(candidates, tolerance, decay_half_life_days: float = 15.0):
    """
    Group price levels within `tolerance` and score by:
    - hit count
    - average volume at hits
    - recency (exponential decay on age)
    """
    if not candidates:
        return []

    # For recency weighting
    now = max(ts for _, _, ts in candidates)
    half_life = pd.Timedelta(days=decay_half_life_days)
    lam = np.log(2) / half_life.total_seconds()

    clusters = []

    # sort by price
    for price, volume, ts in sorted(candidates, key=lambda x: x[0]):
        found_cluster = False

        for cluster in clusters:
            if abs(price - cluster["price"]) <= tolerance:
                cluster["hits"].append(price)
                cluster["volumes"].append(volume)
                cluster["timestamps"].append(ts)
                found_cluster = True
                break

        if not found_cluster:
            clusters.append(
                {
                    "price": price,
                    "hits": [price],
                    "volumes": [volume],
                    "timestamps": [ts],
                }
            )

    for cluster in clusters:
        hit_count = len(cluster["hits"])
        avg_volume = float(np.mean(cluster["volumes"]))

        # recency weights for this cluster
        ages = np.array([(now - ts).total_seconds() for ts in cluster["timestamps"]])
        recency_weights = np.exp(-lam * ages)

        # effective recency factor = average weight in [0, 1]
        recency_factor = float(np.mean(recency_weights))

        # You can tune this; squaring hit_count gives more love to multi-hit levels
        cluster["score"] = (hit_count**2) * avg_volume * recency_factor

        cluster["price"] = float(np.mean(cluster["hits"]))

    return sorted(clusters, key=lambda x: x["score"], reverse=True)
