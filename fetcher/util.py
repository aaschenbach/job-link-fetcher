from __future__ import annotations

import re
import time
from itertools import cycle
from typing import Any

import requests
from bs4 import BeautifulSoup
from curl_cffi import CurlOpt
from curl_cffi import requests as curl_requests
from markdownify import markdownify as md

from fetcher.model import CompensationInterval, JobType


class RotatingProxySession:
    request_timeout = 20
    verify: bool | str = True

    def __init__(self, proxies: list[str] | None = None) -> None:
        proxies = proxies or []
        self.rotates = len(set(proxies)) > 1
        self.proxy_cycle = cycle(map(self._format, proxies)) if proxies else None

    @staticmethod
    def _format(proxy: str) -> dict[str, str]:
        if proxy in ("localhost", "http://localhost"):
            proxy = ""
        elif not re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*://", proxy):
            proxy = f"http://{proxy}"
        return {"http": proxy, "https": proxy}

    def request(self, *args: Any, **kwargs: Any) -> Any:
        if self.proxy_cycle:
            kwargs["proxies"] = next(self.proxy_cycle)
        kwargs.setdefault("verify", self.verify)
        kwargs.setdefault("timeout", self.request_timeout)
        return super().request(*args, **kwargs)  # type: ignore[misc]


class RequestsRotating(RotatingProxySession, requests.Session):
    def __init__(self, proxies: list[str] | None = None) -> None:
        RotatingProxySession.__init__(self, proxies=proxies)
        requests.Session.__init__(self)

    def request(self, *args: Any, **kwargs: Any) -> Any:
        return super().request(*args, **kwargs)


class TLSRotating(RotatingProxySession, curl_requests.Session[curl_requests.Response]):  # type: ignore[misc]
    def __init__(self, proxies: list[str] | None = None) -> None:
        RotatingProxySession.__init__(self, proxies=proxies)
        curl_requests.Session.__init__(
            self,
            impersonate="chrome",
            allow_redirects=False,
            curl_options={CurlOpt.SSL_SESSIONID_CACHE: 0} if self.rotates else None,
        )


def check_status(response: Any) -> None:
    if response.status_code != 200:
        raise ValueError(f"HTTP {response.status_code}")


def _as_markup(text: str) -> str:
    return text if "<" in text else f"<!---->{text}"


def html_to_markdown(html: str | None) -> str | None:
    if not html:
        return None
    return md(_as_markup(html)).strip() or None


def html_to_plain(html: str | None) -> str | None:
    if not html:
        return None
    soup = BeautifulSoup(_as_markup(html), "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip() or None


def extract_emails(text: str | None) -> list[str] | None:
    if not text:
        return None
    found = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    return list(dict.fromkeys(found)) or None


def get_enum_from_job_type(value: str) -> JobType | None:
    try:
        return JobType(value)
    except ValueError:
        return None


annual_factor = {"hourly": 2080, "daily": 260, "weekly": 52, "monthly": 12, "yearly": 1}

_pay_intervals = {
    "HOUR": CompensationInterval.HOURLY,
    "DAY": CompensationInterval.DAILY,
    "WEEK": CompensationInterval.WEEKLY,
    "MONTH": CompensationInterval.MONTHLY,
    "YEAR": CompensationInterval.YEARLY,
    "hourly": CompensationInterval.HOURLY,
    "HOURLY": CompensationInterval.HOURLY,
    "ANNUAL": CompensationInterval.YEARLY,
    "MONTHLY": CompensationInterval.MONTHLY,
    "yr": CompensationInterval.YEARLY,
    "/yr": CompensationInterval.YEARLY,
    "/mo": CompensationInterval.MONTHLY,
    "/wk": CompensationInterval.WEEKLY,
    "/hr": CompensationInterval.HOURLY,
}


def parse_interval(raw: str | None) -> CompensationInterval | None:
    return _pay_intervals.get(raw or "")


def sleep_between_requests(delay: float = 2.0) -> None:
    time.sleep(delay)
