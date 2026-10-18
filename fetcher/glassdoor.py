from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from fetcher.model import CompensationInterval, JobDetail, Location
from fetcher.util import (
    TLSRotating,
    check_status,
    extract_emails,
    get_enum_from_job_type,
    html_to_markdown,
    html_to_plain,
    parse_interval,
)

_HEADERS = {
    "gd-csrf-token": "Ft6oHEWlRZrxDww95Cpazw:0pGUrkb2y3TyOpAIqF2vbPmUXoXVkD3oEGDVkvfeCerceQ5-n8mBg3BovySUIjmCPHCaW0H2nQVdqzbtsYqf4Q:wcqRqeegRUa9MVLJGyujVXB7vWFPjdaS1CtrrzJq-ok",
}

_PAY_INTERVALS = {
    "ANNUAL": CompensationInterval.YEARLY,
    "MONTHLY": CompensationInterval.MONTHLY,
    "HOURLY": CompensationInterval.HOURLY,
}

_DOMAINS = {
    "www.glassdoor.com.br": "www.glassdoor.com.br",
    "glassdoor.com.br": "www.glassdoor.com.br",
    "www.glassdoor.com": "www.glassdoor.com",
    "glassdoor.com": "www.glassdoor.com",
    "www.glassdoor.co.uk": "www.glassdoor.co.uk",
    "www.glassdoor.de": "www.glassdoor.de",
    "www.glassdoor.fr": "www.glassdoor.fr",
    "www.glassdoor.com.au": "www.glassdoor.com.au",
    "www.glassdoor.ca": "www.glassdoor.ca",
    "www.glassdoor.co.in": "www.glassdoor.co.in",
}

_DETAIL_QUERY = """
    j%s: jobView(listingId: %s, contextHolder: {queryString: "q", pageTypeEnum: SERP}) {
        header {
            adOrderSponsorshipLevel
            ageInDays
            employer { id }
            employerNameFromSearch
            jobTypeKeys
            locationName
            locationType
            payCurrency
            payPeriod
            payPeriodAdjustedPay { p10 p90 }
            rating
            remoteWorkTypes
        }
        job {
            jobTitleText
            listingId
            description
        }
        map { country }
        overview {
            headquarters
            overview { description }
            primaryIndustry { industryName }
            revenue
            size
            squareLogoUrl
            website
        }
    }
"""


def extract_listing_id(url: str) -> tuple[str, str]:
    """
    Extrai (listing_id, base_url) de uma URL do Glassdoor.
    Suporta:
      - /job-listing/j?jl=...
      - /partner/jobListing.htm?jobListingId=...
      - /Job/...j?jl=...
    """
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    domain = _DOMAINS.get(hostname, "www.glassdoor.com")
    base_url = f"https://{domain}"

    qs = parse_qs(parsed.query)
    for param in ("jl", "jobListingId"):
        if param in qs:
            return qs[param][0], base_url

    path_match = re.search(r"[?&]jl=(\d+)", url)
    if path_match:
        return path_match.group(1), base_url

    raise ValueError(f"Não foi possível extrair o listing ID da URL: {url}")


def fetch(
    url: str,
    proxies: list[str] | None = None,
    ca_cert: str | None = None,
    user_agent: str | None = None,
    description_format: str = "markdown",
) -> JobDetail:
    listing_id, base_url = extract_listing_id(url)

    session = TLSRotating(proxies)
    if ca_cert:
        session.verify = ca_cert
    headers = dict(_HEADERS)
    if user_agent:
        headers["user-agent"] = user_agent
    session.headers.update(headers)

    # Inicializa sessão TLS/cookies via endpoint leve (necessário antes do /graph)
    init_resp = session.get(
        f"{base_url}/autocomplete/location"
        "?locationTypeFilters=CITY,STATE,COUNTRY&caller=jobs&term="
    )
    if init_resp.status_code not in (200, 301, 302):
        raise ValueError(f"Glassdoor bloqueou a inicialização de sessão: HTTP {init_resp.status_code}")

    query = "query JobDetails {" + (_DETAIL_QUERY % (listing_id, listing_id)) + "}"
    response = session.post(
        f"{base_url}/graph",
        json=[{"operationName": "JobDetails", "variables": {}, "query": query}],
    )
    check_status(response)

    data = response.json()
    view_key = f"j{listing_id}"
    view = (data[0].get("data") or {}).get(view_key) if isinstance(data, list) else None
    if not view:
        raise ValueError(f"Glassdoor não retornou dados para listing ID: {listing_id}")

    return _build_job(view, listing_id, base_url, description_format)


def _build_job(
    view: dict,
    listing_id: str,
    base_url: str,
    description_format: str,
) -> JobDetail:
    header = view.get("header") or {}
    overview_raw = view.get("overview") or {}
    job_raw = view.get("job") or {}
    country = (view.get("map") or {}).get("country")

    # "description" é uma string HTML direto no nó job
    html = job_raw.get("description")
    title = job_raw.get("jobTitleText")

    if description_format == "markdown":
        description = html_to_markdown(html)
    elif description_format == "plain":
        description = html_to_plain(html)
    else:
        description = html

    emails = extract_emails(html)

    age = header.get("ageInDays") or 0
    date_posted = (datetime.now(timezone.utc) - timedelta(days=age)).date()

    job_types = [
        jt
        for key in (header.get("jobTypeKeys") or [])
        if (jt := get_enum_from_job_type(key.rpartition(".")[2]))
    ]

    company_id = (header.get("employer") or {}).get("id")
    website = overview_raw.get("website")
    if website and not website.startswith("http"):
        website = f"https://{website}"

    location = _parse_location(header.get("locationName"), header.get("locationType"), country)

    pay = header.get("payPeriodAdjustedPay") or {}
    interval = _PAY_INTERVALS.get(header.get("payPeriod") or "")
    min_amount = round(pay["p10"], 2) if "p10" in pay else None
    max_amount = round(pay["p90"], 2) if "p90" in pay else None

    is_remote = (
        "WORK_FROM_HOME" in (header.get("remoteWorkTypes") or [])
        or header.get("locationName") == "Remote"
    )

    overview = overview_raw.get("overview") or {}
    industry_raw = (overview_raw.get("primaryIndustry") or {}).get("industryName")

    return JobDetail(
        site="glassdoor",
        job_url=f"{base_url}/job-listing/j?jl={listing_id}",
        title=title,
        company=header.get("employerNameFromSearch"),
        company_url=(
            f"{base_url}/Overview/W-EI_IE{company_id}.htm" if company_id else None
        ),
        company_logo=overview_raw.get("squareLogoUrl"),
        company_url_direct=website,
        company_addresses=overview_raw.get("headquarters"),
        company_num_employees=overview_raw.get("size"),
        company_revenue=overview_raw.get("revenue"),
        company_description=overview.get("description"),
        company_industry=industry_raw,
        company_rating=header.get("rating"),
        location=location,
        date_posted=date_posted,
        job_type=job_types or None,
        interval=interval,
        min_amount=min_amount,
        max_amount=max_amount,
        currency=header.get("payCurrency"),
        is_remote=is_remote,
        description=description,
        emails=emails,
    )


def _parse_location(name: str | None, kind: str | None, country: str | None) -> Location | None:
    if not name or name == "Remote":
        return None
    if kind == "N":
        return Location(country=country or name)
    if kind == "S":
        return Location(state=name, country=country)
    city, *rest = name.split(", ")
    return Location(city=city, state=rest[-1] if rest else None, country=country)
