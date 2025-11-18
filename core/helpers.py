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
        low = row["l"]
        high = row["h"]
        volume = row["v"]

        # Check for isolated low; this low must be lower than lows of surrounding candles
        is_isolated_low = all(
            low < df.iloc[i - j]["l"] and low < df.iloc[i + j]["l"]
            for j in range(1, min_separation + 1)
        )

        if is_isolated_low:
            support_candidates.append((low, volume))

        # Check for isolated high; this high must be higher than highs of surrounding candles
        is_isolated_high = all(
            high > df.iloc[i - j]["h"] and high > df.iloc[i + j]["h"]
            for j in range(1, min_separation + 1)
        )

        if is_isolated_high:
            resistance_candidates.append((high, volume))

    # Return top support and resistance levels
    top_support = _cluster_levels(support_candidates, price_tolerance)[:top_n]
    top_resistance = _cluster_levels(resistance_candidates, price_tolerance)[:top_n]

    return top_support, top_resistance


def _cluster_levels(candidates, tolerance):
    """
    Helper method to group price levels within `tolerance` and score them based on
    - number of hits (confirmations)
    - average volume during those hits
    """
    clusters = []

    for price, volume in sorted(candidates):
        found_cluster = False

        # Try to match this level to an existing cluster
        for cluster in clusters:
            if abs(price - cluster["price"]) <= tolerance:
                cluster["hits"].append(price)
                cluster["volumes"].append(volume)
                found_cluster = True
                break

        # If no matching cluster, start a new one
        if not found_cluster:
            clusters.append(
                {
                    "price": price,
                    "hits": [price],
                    "volumes": [volume],
                }
            )

    # Calculate a score for each cluster
    for cluster in clusters:
        hit_count = len(cluster["hits"])
        avg_volume = np.mean(cluster["volumes"])
        cluster["score"] = hit_count * avg_volume
        # Average the cluster's price level
        cluster["price"] = np.mean(cluster["hits"])

    # Sort clusters by score, highest first
    return sorted(clusters, key=lambda x: x["score"], reverse=True)
