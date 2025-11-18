class Level:
    def __init__(
        self,
        value,
        name=None,
        support=True,
        resistance=True,
        proximity_threshold=2.5,
        reward_points=10,
        risk_points=10,
    ):
        self.value = value
        self.name = name
        self.support = support
        self.resistance = resistance
        self.proximity_threshold = proximity_threshold
        self.reward_points = reward_points
        self.risk_points = risk_points

    def update(self, value):
        self.value = value


class SignalDispatcher:
    def __init__(self, logger, levels=[]):
        self.logger = logger

        # Convert levels to dictionary for fast lookups by value or name depending on if the level
        # is static or dynamic.
        self.levels = {}
        for level in levels:
            if level.name is None:
                self.levels[level.value] = level
            else:
                self.levels[level.name] = level

        self.last_level_traded = None

    def check(self, price, timestamp=None):
        if not self.levels:
            return None

        # Check if the current price is in proximity to any of our levels and signal accordingly
        signals = []
        for level_key in self.levels:
            level = self.levels[level_key]
            distance = abs(price - level.value)

            # If the current price is close enough to the level, then we may need to emit a LONG or
            # SHORT signal.
            if distance <= level.proximity_threshold:
                # Emit a SHORT signal if the current price is slightly under a resistance level
                if price < level.value and level.resistance:
                    signals.append((level_key, level, distance, "SHORT"))
                # Emit a LONG signal if the current price is slightly over a support level
                elif price > level.value and level.support:
                    signals.append((level_key, level, distance, "LONG"))

        # If signals is empty, then there is nothing to act on for now
        if not signals:
            return None

        # Pick the closest qualifying level
        level_key, level, _, direction = min(signals, key=lambda x: x[2])

        # Abort if this is a retest of the level
        if self.last_level_traded == level_key:
            return None

        entry = price

        take_profit = (
            entry + level.reward_points
            if direction == "LONG"
            else entry - level.reward_points
        )
        take_profit = round(take_profit, 2)

        stop_loss = (
            entry - level.risk_points
            if direction == "LONG"
            else entry + level.risk_points
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

    def reset(self):
        self.last_level_traded = None

    def reset_on_new_level(self, level_name):
        if self.last_level_traded != level_name:
            self.last_level_traded = None
