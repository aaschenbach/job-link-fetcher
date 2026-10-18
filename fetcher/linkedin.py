from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from fetcher.model import CompensationInterval, JobDetail, Location
from fetcher.util import (
    RequestsRotating,
    check_status,
    extract_emails,
    get_enum_from_job_type,
    html_to_markdown,
    html_to_plain,
    annual_factor,
)

_HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "accept-language": "en-US,en;q=0.9",
}

_BASE = "https://www.linkedin.com"

_PAY_INTERVALS = {
    "/yr": CompensationInterval.YEARLY,
    "/mo": CompensationInterval.MONTHLY,
    "/wk": CompensationInterval.WEEKLY,
    "/hr": CompensationInterval.HOURLY,
}

_CURRENCIES = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY", "₹": "INR"}

_SALARY_RE = re.compile(
    r"([^\d\s]+) ?([\d,]+\.\d\d)(/\w+) - [^\d\s]+ ?([\d,]+\.\d\d)/\w+"
)
_SALARY_RANGE_RE = re.compile(
    r"\$([\d,]+(?:\.\d+)?)(K?)\s*[-–]\s*\$([\d,]+(?:\.\d+)?)(K?)"
)

_HOURLY_THRESHOLD = 1000
_MONTHLY_THRESHOLD = 10000
_LOWER_LIMIT = 10000
_UPPER_LIMIT = 700000


def extract_job_id(url: str) -> str | None:
    """Extrai o ID numérico da vaga a partir de uma URL do LinkedIn."""
    path = urlparse(url).path
    match = re.search(r"/(\d+)/?$", path)
    return match.group(1) if match else None


def fetch(
    url: str,
    proxies: list[str] | None = None,
    ca_cert: str | None = None,
    user_agent: str | None = None,
    description_format: str = "markdown",
) -> JobDetail:
    job_id = extract_job_id(url)
    if not job_id:
        raise ValueError(f"Não foi possível extrair o ID da vaga da URL: {url}")

    session = RequestsRotating(proxies)
    if ca_cert:
        session.verify = ca_cert
    headers = dict(_HEADERS)
    if user_agent:
        headers["user-agent"] = user_agent
    session.headers.update(headers)

    response = session.get(f"{_BASE}/jobs/view/{job_id}")
    check_status(response)

    path = urlparse(response.url).path
    if not path.startswith("/jobs/view/"):
        raise ValueError(f"LinkedIn redirecionou para {path} (possível bloqueio)")

    soup = BeautifulSoup(response.text, "html.parser")

    title_tag = soup.find("h1", class_=re.compile("job-details-jobs-unified-top-card__job-title"))
    if title_tag is None:
        title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else None

    company_tag = soup.find("a", class_=re.compile("job-details-jobs-unified-top-card__company-name"))
    if company_tag is None:
        company_tag = soup.find("span", class_=re.compile("topcard__org-name"))
    company = company_tag.get_text(strip=True) if company_tag else None

    company_url_tag = company_tag.get("href") if company_tag and company_tag.name == "a" else None
    company_url = (
        company_url_tag.split("?")[0]
        if company_url_tag and company_url_tag.startswith("http")
        else (f"{_BASE}{company_url_tag}" if company_url_tag else None)
    )

    logo_tag = soup.find("img", class_=re.compile("artdeco-entity-image"))
    company_logo = logo_tag.get("data-delayed-url") if logo_tag else None

    div_desc = soup.find("div", class_="show-more-less-html__markup")
    if div_desc:
        div_desc.attrs.clear()
    html = div_desc.prettify(formatter="html") if div_desc else None

    if description_format == "markdown":
        description = html_to_markdown(html)
    elif description_format == "plain":
        description = html_to_plain(html)
    else:
        description = html

    emails = extract_emails(html)

    salary_tag = soup.find("div", class_="compensation__salary")
    pay = _parse_salary(salary_tag.get_text() if salary_tag else "")

    if not pay.get("min_amount") and not pay.get("max_amount"):
        pay = _guess_salary(html_to_plain(html))

    job_type = None
    employment_type = _criteria(soup, "Employment type")
    if employment_type:
        jt = get_enum_from_job_type(employment_type.lower().replace("-", "").replace(" ", ""))
        if jt:
            job_type = [jt]

    job_level = _criteria(soup, "Seniority level")
    job_function = _criteria(soup, "Job function")
    company_industry = _criteria(soup, "Industries")

    location_tag = soup.find("span", class_=re.compile("job-details-jobs-unified-top-card__bullet"))
    location_text = location_tag.get_text(strip=True) if location_tag else None
    location = _parse_location(location_text) if location_text else None

    return JobDetail(
        site="linkedin",
        job_url=f"{_BASE}/jobs/view/{job_id}",
        title=title,
        company=company,
        company_url=company_url,
        company_logo=company_logo,
        location=location,
        job_type=job_type,
        job_level=job_level.lower() if job_level else None,
        job_function=job_function,
        company_industry=company_industry,
        description=description,
        emails=emails,
        **pay,
    )


def _parse_location(text: str) -> Location | None:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) >= 3:
        return Location(city=parts[0], state=parts[1], country=parts[-1])
    if len(parts) == 2:
        return Location(city=parts[0], country=parts[1])
    return Location(city=parts[0]) if parts else None


def _parse_salary(text: str) -> dict:
    match = _SALARY_RE.fullmatch(" ".join(text.split()))
    if not match:
        return {}
    currency_sym, low, interval_str, high = match.groups()
    interval = _PAY_INTERVALS.get(interval_str)
    return {
        "interval": interval,
        "min_amount": float(low.replace(",", "")),
        "max_amount": float(high.replace(",", "")),
        "currency": _CURRENCIES.get(currency_sym, currency_sym),
    }


def _guess_salary(text: str | None) -> dict:
    match = _SALARY_RANGE_RE.search(text or "")
    if not match:
        return {}
    low = int(float(match.group(1).replace(",", "")))
    high = int(float(match.group(3).replace(",", "")))
    if match.group(2):
        low *= 1000
    if match.group(4):
        high *= 1000
    if low < _HOURLY_THRESHOLD:
        interval = CompensationInterval.HOURLY
    elif low < _MONTHLY_THRESHOLD:
        interval = CompensationInterval.MONTHLY
    else:
        interval = CompensationInterval.YEARLY
    factor = annual_factor[interval.value]
    if not (_LOWER_LIMIT <= low * factor < high * factor <= _UPPER_LIMIT):
        return {}
    return {
        "interval": interval,
        "min_amount": low,
        "max_amount": high,
        "currency": "USD",
    }


def _criteria(soup: BeautifulSoup, label: str) -> str | None:
    """Extrai valor de um critério da sidebar (Employment type, Seniority level etc.)."""
    for item in soup.find_all("li", class_=re.compile("description__job-criteria-item")):
        header = item.find("h3")
        if header and label.lower() in header.get_text(strip=True).lower():
            value_tag = item.find("span")
            if value_tag:
                return value_tag.get_text(strip=True)
    return None
