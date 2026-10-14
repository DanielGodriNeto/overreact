"""Polite outbound HTTP shared by the recorder and the news ear: throttle detection, safe Retry-After, backoff."""
import requests

UA = "overreact-research/0.1 (personal, non-commercial)"
THROTTLE_CODES = (403, 418, 429)


class Throttled(requests.RequestException):
    """The server asked us to slow down (or banned us). Subclass so every RequestException handler also stops on it."""

    def __init__(self, status: int, retry_after: float | None):
        super().__init__(f"HTTP {status}")
        self.retry_after = retry_after


def retry_after(headers) -> float | None:
    value = headers.get("Retry-After", "")
    return float(value) if value.isdigit() else None  # HTTP-date form is ignored, backoff applies instead


def raise_for_throttle(resp: requests.Response) -> None:
    if resp.status_code in THROTTLE_CODES:
        raise Throttled(resp.status_code, retry_after(resp.headers))


def next_delay(interval_s: float, fails: int, throttled: bool, retry_s: float | None) -> float:
    """Seconds until the next call. 3 throttles in a row pause 15 min; never hammer a host."""
    if fails == 0:
        return interval_s
    if throttled:
        return 900.0 if fails >= 3 else max(retry_s or 0, 60.0 * 2 ** (fails - 1))
    return min(300.0, interval_s * 2 ** fails)


def get_json(url: str, params: dict | None = None) -> list | dict:
    resp = requests.get(url, params=params, timeout=10, headers={"User-Agent": UA})
    raise_for_throttle(resp)
    resp.raise_for_status()
    return resp.json()
