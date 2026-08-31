"""
@file rate_limit.py
@description Limitador de intentos en memoria (sliding window) para endpoints
sensibles como /auth/login. No requiere Redis: pensado para un único proceso
backend. Si en el futuro se escala a múltiples workers/instancias, este estado
deja de compartirse entre procesos y habría que migrar a un backend externo
(Redis, etc.).
"""
import time
from collections import defaultdict
from threading import Lock


class SlidingWindowLimiter:
    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def _prune(self, key: str, now: float) -> list[float]:
        cutoff = now - self.window_seconds
        hits = [t for t in self._hits[key] if t > cutoff]
        self._hits[key] = hits
        return hits

    def is_blocked(self, key: str) -> tuple[bool, int]:
        """Retorna (bloqueado, segundos_restantes) sin registrar un nuevo intento."""
        now = time.monotonic()
        with self._lock:
            hits = self._prune(key, now)
            if len(hits) >= self.max_attempts:
                retry_after = int(self.window_seconds - (now - hits[0]))
                return True, max(retry_after, 1)
            return False, 0

    def register_attempt(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._prune(key, now)
            self._hits[key].append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)
