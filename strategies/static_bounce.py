import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from tabulate import tabulate

from core import Tick


class StaticLevel:
    def __init__(
        self,
        value: float,
        hits: List[float],
        score: float,
        support: Optional[bool] = True,
        resistance: Optional[bool] = True,
    ) -> None:
        self.value = value
        self.hits = hits
        self.score = score
        self.support = support
        self.resistance = resistance

    def update(self, value: float) -> None:
        self.value = value


class StaticBounce:
    def __init__(
        self,
        logger: logging.Logger,
        candles: List[Dict[str, Any]],
        tick_size: float,
        proximity_threshold: int,
        reward_ticks: int,
        risk_ticks: int,
        tick_tolerance: int,
        min_separation: int,
        top_n: int,
        decay_half_life_days: float,
    ) -> None:
        # Logs trade signals
        self.logger = logger

        # Contains data for historical analysis
        self.candles = candles

        # Tick size for the instrument being traded
        self.tick_size = tick_size

        # Bounce parameters
        self.proximity_threshold = proximity_threshold
        self.reward_ticks = reward_ticks
        self.risk_ticks = risk_ticks

        # Static level calculation parameters applied to historical candles
        self.tick_tolerance = tick_tolerance
        self.min_separation = min_separation
        self.top_n = top_n
        self.decay_half_life_days = decay_half_life_days

        # Static levels
        self.support: List[StaticLevel] = []
        self.resistance: List[StaticLevel] = []

        self.calculate_static_levels()

        # Convert support and resistance to a single dictionary for fast lookups by value when
        # checking for signals.
        # Support and resistan
        # Because this is a demo strategy, we will treat support and resistance the same.
        self.levels = {}
        for lvl in self.support + self.resistance:
            self.levels[lvl.value] = lvl

        # Last level traded to avoid retests
        self.last_level_traded: float | None = None

    def check(self, tick: Tick, timestamp: Any = None) -> Dict[str, Any] | None:
        if not self.levels:
            return None

        # Check if the current price is in proximity to any of our levels and signal accordingly
        signals = []
        for level_key in self.levels:
            level = self.levels[level_key]
            distance = abs(tick.price - level.value)

            # If the current price is close enough to the level, then we may need to emit a LONG or
            # SHORT signal.
            if distance <= (self.proximity_threshold * self.tick_size):
                # Emit a SHORT signal if the current price is slightly under a resistance level
                if tick.price < level.value and level.resistance:
                    signals.append((level_key, level, distance, "SHORT"))
                # Emit a LONG signal if the current price is slightly over a support level
                elif tick.price > level.value and level.support:
                    signals.append((level_key, level, distance, "LONG"))

        # If signals is empty, then there is nothing to act on for now
        if not signals:
            return None

        # Pick the closest qualifying level
        level_key, level, _, direction = min(signals, key=lambda x: x[2])

        # Abort if this is a retest of the level
        if self.last_level_traded == level_key:
            return None

        entry = tick.price

        take_profit = (
            entry + self.reward_ticks * self.tick_size
            if direction == "LONG"
            else entry - self.reward_ticks * self.tick_size
        )
        take_profit = round(take_profit, 2)

        stop_loss = (
            entry - self.risk_ticks * self.tick_size
            if direction == "LONG"
            else entry + self.risk_ticks * self.tick_size
        )
        stop_loss = round(stop_loss, 2)

        self.logger.info(
            f"{direction} signal from {level_key} at {entry}",
            extra={
                "timestamp": timestamp,
                "event": "signal_detected",
                "direction": direction,
                "entry": entry,
                "take_profit": take_profit,
                "stop_loss": stop_loss,
                "trigger_level": level_key,
            },
        )

        self.last_level_traded = level_key

        return {
            "timestamp": timestamp,
            "direction": direction,
            "entry": entry,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "level": level_key,
        }

    def reset(self) -> None:
        self.last_level_traded = None

    def calculate_static_levels(self) -> None:
        # Convert the raw candle data from a list of dicts into a DataFrame
        df = pd.DataFrame(self.candles)
        df["t"] = pd.to_datetime(df["t"])
        df.set_index("t", inplace=True)

        support_candidates = []
        resistance_candidates = []
        for i in range(self.min_separation, len(df) - self.min_separation):
            row = df.iloc[i]
            ts = df.index[i]
            low = row["l"]
            high = row["h"]
            volume = row["v"]

            # Check for isolated low; this low must be lower than lows of surrounding candles
            is_isolated_low = all(
                low < df.iloc[i - j]["l"] and low < df.iloc[i + j]["l"]
                for j in range(1, self.min_separation + 1)
            )

            if is_isolated_low:
                support_candidates.append((low, volume, ts))

            # Check for isolated high; this high must be higher than highs of surrounding candles
            is_isolated_high = all(
                high > df.iloc[i - j]["h"] and high > df.iloc[i + j]["h"]
                for j in range(1, self.min_separation + 1)
            )

            if is_isolated_high:
                resistance_candidates.append((high, volume, ts))

        # Return top support and resistance levels as a list of dicts
        support_dicts = self._cluster_levels(support_candidates)[: self.top_n]
        resistance_dicts = self._cluster_levels(resistance_candidates)[: self.top_n]

        # Create StaticLevel instances
        self.support = [
            StaticLevel(
                round(lvl["price"], 2),
                lvl["hits"],
                lvl["score"],
                support=True,
                resistance=True,
            )
            for lvl in support_dicts
        ]
        self.resistance = [
            StaticLevel(
                round(lvl["price"], 2),
                lvl["hits"],
                lvl["score"],
                support=True,
                resistance=True,
            )
            for lvl in resistance_dicts
        ]

    def print_static_levels(self) -> None:
        headers = ["Level", "Hits", "Score"]

        print("\nTop Support Levels:")
        print(
            tabulate(
                [
                    (f"{lvl.value:.2f}", len(lvl.hits), f"{lvl.score:.2f}")
                    for lvl in self.support
                ],
                headers,
                tablefmt="pretty",
            )
        )

        print("\nTop Resistance Levels:")
        print(
            tabulate(
                [
                    (f"{lvl.value:.2f}", len(lvl.hits), f"{lvl.score:.2f}")
                    for lvl in self.resistance
                ],
                headers,
                tablefmt="pretty",
            )
        )

    def _cluster_levels(self, candidates) -> List[Dict[str, Any]]:
        if not candidates:
            return []

        # For recency weighting
        now = max(ts for _, _, ts in candidates)
        half_life = pd.Timedelta(days=self.decay_half_life_days)
        lam = np.log(2) / half_life.total_seconds()

        clusters: List[Dict[str, Any]] = []

        # Sort by price
        for price, volume, ts in sorted(candidates, key=lambda x: x[0]):
            found_cluster = False

            for cluster in clusters:
                if (
                    abs(price - cluster["price"])
                    <= self.tick_tolerance * self.tick_size
                ):
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
            ages = np.array(
                [(now - ts).total_seconds() for ts in cluster["timestamps"]]
            )
            recency_weights = np.exp(-lam * ages)

            # effective recency factor = average weight in [0, 1]
            recency_factor = float(np.mean(recency_weights))

            # You can tune this; squaring hit_count gives more love to multi-hit levels
            cluster["score"] = (hit_count**2) * avg_volume * recency_factor

            cluster["price"] = float(np.mean(cluster["hits"]))

        return sorted(clusters, key=lambda x: x["score"], reverse=True)
