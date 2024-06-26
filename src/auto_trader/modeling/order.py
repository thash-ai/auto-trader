from datetime import datetime
from enum import Enum
from typing import Optional

import pandas as pd


class PositionType(Enum):
    LONG = "long"
    SHORT = "short"


class Order:
    def __init__(
        self,
        position_type: PositionType,
        entry_time: datetime,
        entry_rate: float,
    ):
        self.position_type = position_type
        self.entry_time = entry_time
        self.entry_rate = entry_rate
        self.exit_time: Optional[datetime] = None
        self.exit_rate: Optional[float] = None

    def exit(
        self,
        exit_time: datetime,
        exit_rate: float,
    ) -> None:
        self.exit_time = exit_time
        self.exit_rate = exit_rate

    @property
    def gain(self) -> float:
        assert self.exit_rate is not None
        rate_diff = self.exit_rate - self.entry_rate
        if self.position_type == PositionType.LONG:
            return rate_diff
        elif self.position_type == PositionType.SHORT:
            return -rate_diff

    def __repr__(self) -> str:
        gain = None
        if self.exit_rate is not None:
            gain = self.gain
        return (
            f"{self.position_type} ({self.entry_time} ~ {self.exit_time}) "
            f"{self.entry_rate} -> {self.exit_rate} ({gain})"
        )


class OrderSimulator:
    def __init__(
        self,
        start_hour: int,
        end_hour: int,
        thresh_losscut: float,
    ):
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.thresh_losscut = thresh_losscut
        self.order_history: list[Order] = []
        self.open_position: Optional[Order] = None

    def step(
        self,
        dt: datetime,
        rate: float,
        long_entry: bool,
        long_exit: bool,
        short_entry: bool,
        short_exit: bool,
    ) -> None:
        is_open = (self.start_hour <= dt.hour < self.end_hour) and (
            dt.month,
            dt.day,
        ) != (12, 25)

        # exit の条件: ポジションをもっている and (取引時間外 or モデルが決済を選択 or 損切り)
        if (
            self.open_position is not None
            and self.open_position.position_type == PositionType.LONG
            and (
                not is_open
                or long_exit
                or self.open_position.entry_rate - rate >= self.thresh_losscut
            )
        ) or (
            self.open_position is not None
            and self.open_position.position_type == PositionType.SHORT
            and (
                not is_open
                or short_exit
                or rate - self.open_position.entry_rate >= self.thresh_losscut
            )
        ):
            self.open_position.exit(dt, rate)
            self.order_history.append(self.open_position)
            self.open_position = None

        # open の条件: 取引時間内 and ポジションを持っていない and モデルが購入を選択
        if is_open and self.open_position is None:
            if long_entry:
                self.open_position = Order(PositionType.LONG, dt, rate)
            elif short_entry:
                self.open_position = Order(PositionType.SHORT, dt, rate)

    def export_results(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "position_type": order.position_type.value,
                "entry_time": order.entry_time,
                "exit_time": order.exit_time,
                "entry_rate": order.entry_rate,
                "exit_rate": order.exit_rate,
                "gain": order.gain,
            }
            for order in self.order_history
        )
