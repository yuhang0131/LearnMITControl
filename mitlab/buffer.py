"""定长滚动数据缓冲（numpy，无 Qt 依赖），用于实时绘图。"""
from __future__ import annotations

from typing import Dict, Iterable, Optional

import numpy as np


class SignalBuffer:
    def __init__(self, fields: Iterable[str], capacity: int = 40000):
        self.fields = tuple(fields)
        self.cap = int(capacity)
        self._d = {k: np.empty(2 * self.cap) for k in self.fields}
        self._s = 0   # 有效数据起点
        self._n = 0   # 有效数据终点（不含）

    def clear(self) -> None:
        self._s = self._n = 0

    def __len__(self) -> int:
        return self._n - self._s

    def extend(self, logs: Dict[str, list]) -> None:
        m = len(logs["t"])
        if m == 0:
            return
        if m > self.cap:
            logs = {k: v[-self.cap:] for k, v in logs.items()}
            m = self.cap
        if self._n + m > 2 * self.cap:      # 空间不足：把最近的数据挪到开头
            keep = min(len(self), self.cap - m)
            for k in self.fields:
                a = self._d[k]
                a[:keep] = a[self._n - keep:self._n]
            self._s, self._n = 0, keep
        for k in self.fields:
            self._d[k][self._n:self._n + m] = logs[k]
        self._n += m
        if len(self) > self.cap:
            self._s = self._n - self.cap

    def view(self, t_min: Optional[float] = None) -> Dict[str, np.ndarray]:
        s, n = self._s, self._n
        if t_min is not None and n > s:
            s = s + int(np.searchsorted(self._d["t"][s:n], t_min))
        return {k: self._d[k][s:n] for k in self.fields}
