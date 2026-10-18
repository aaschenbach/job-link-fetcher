from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from fetcher.model import CompensationInterval, JobDetail, JobType, Location
from fetcher.util import (
    RequestsRotating,
    check_status,
    extract_emails,
    html_to_markdown,
    html_to_plain,
    parse_interval,
)

_HEADERS = {
    "content-type": "application/json",
    "indeed-api-key": "161092c2017b5bbab13edb12461a62d5a833871e7cad6d9d475304573de67ac8",
    "accept": "application/json",
    "accept-language": "en-US,en;q=0.9",
    "user-agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6_1 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Indeed App 193.1"
    ),
    "indeed-app-info": "appv=193.1; appid=com.indeed.jobsearch; osv=16.6.1; os=ios; dtype=phone",
}

_API_URL = "https://apis.indeed.com/graphql"

_COUNTRY_CODES = {
    "www": ("US", "en"),
    "br": ("BR", "pt"),
    "uk": ("GB", "en"),
    "ca": ("CA", "en"),
    "au": ("AU", "en"),
    "de": ("DE", "de"),
    "fr": ("FR", "fr"),
    "es": ("ES", "es"),
    "mx": ("MX", "es"),
    "ar": ("AR", "es"),
    "in": ("IN", "en"),
}

_JOB_FIELDS = """
    key title sourceEmployerName dateOnIndeed
    description { html }
    location { countryCode admin1Code city }
    compensation {
        estimated { currencyCode baseSalary { unitOfWork range { ... on Range { min max } ... on AtLeast { min } ... on AtMost { max } ... on Exactly { value } } } }
        baseSalary { unitOfWork range { ... on Range { min max } ... on AtLeast { min } ... on AtMost { max } ... on Exactly { value } } }
        currencyCode
    }
    attributes { key }
    employer {
        relativeCompanyPageUrl name
        ugcStats { ratings { overallRating { value count } } }
        dossier {
            employerDetails { addresses industry employeesLocalizedLabel revenueLocalizedLabel briefDescription }
            images { squareLogoUrl }
            links { corporateWebsite }
        }
    }
    recruit { viewJobUrl }
"""

_JOB_SEARCH_QUERY = """
query GetJobData {
    jobSearch(
        limit: 1
        filters: [{ keyword: { field: "jobKey", keys: ["%s"] } }]
    ) {
        results { job {""" + _JOB_FIELDS + """} }
    }
}
"""

_JOB_TYPES_BY_KEY = {
    "CF3CP": JobType.FULL_TIME,
    "75GKK": JobType.PART_TIME,
    "NJXCK": JobType.CONTRACT,
    "T9BXE": JobType.CONTRACT,
    "T65DZ": JobType.CONTRACT,
    "VDTG7": JobType.INTERNSHIP,
    "4HKF7": JobType.TEMPORARY,
    "CJWTS": JobType.TEMPORARY,
    "TQKYQ": JobType.PER_DIEM,
    "UXQZ8": JobType.VOLUNTEER,
    "5QWDV": JobType.FULL_TIME,
}

_REMOTE_KEY = "DSQF7"


def extract_job_key(url: str) -> tuple[str, str]:
    """
    Retorna (job_key, subdomain) a partir de uma URL do Indeed.
    Suporta /viewjob?jk=..., /rc/clk?jk=..., /pagead/clk?jk=...,
    partner URLs com vjk=..., e URLs diretas /jobs/view/...
    """
    parsed = urlparse(url)
    subdomain = parsed.hostname.split(".")[0] if parsed.hostname else "www"
    subdomain = subdomain if subdomain in _COUNTRY_CODES else "www"

    qs = parse_qs(parsed.query)
    for param in ("jk", "vjk"):
        if param in qs:
            return qs[param][0], subdomain

    path_match = re.search(r"/jobs/view/([a-f0-9]+)", parsed.path)
    if path_match:
        return path_match.group(1), subdomain

    raise ValueError(f"Não foi possível extrair o job key da URL: {url}")


def fetch(
    url: str,
    proxies: list[str] | None = None,
    ca_cert: str | None = None,
    user_agent: str | None = None,
    description_format: str = "markdown",
) -> JobDetail:
    job_key, subdomain = extract_job_key(url)
    country_code, language = _COUNTRY_CODES.get(subdomain, ("US", "en"))

    base_url = f"https://{subdomain}.indeed.com" if subdomain not in ("www",) else "https://www.indeed.com"

    session = RequestsRotating(proxies)
    if ca_cert:
        session.verify = ca_cert
    headers = dict(_HEADERS)
    headers["indeed-co"] = country_code
    headers["indeed-locale"] = f"{language}-{country_code}"
    if user_agent:
        headers["user-agent"] = user_agent
    session.headers.update(headers)

    response = session.post(
        _API_URL,
        json={"query": _JOB_SEARCH_QUERY % job_key},
    )
    check_status(response)
    data = response.json()

    results = (((data.get("data") or {}).get("jobSearch") or {}).get("results") or [])
    raw = results[0].get("job") if results else None
    if not raw:
        raise ValueError(f"Vaga não encontrada para job key: {job_key}")

    return _build_job(raw, job_key, base_url, country_code, description_format)



def _build_job(
    raw: dict,
    job_key: str,
    base_url: str,
    country_code: str,
    description_format: str,
) -> JobDetail:
    html = (raw.get("description") or {}).get("html")

    if description_format == "markdown":
        description = html_to_markdown(html)
    elif description_format == "plain":
        description = html_to_plain(html)
    else:
        description = html

    emails = extract_emails(html)

    loc = raw.get("location") or {}
    location = Location(
        city=loc.get("city"),
        state=loc.get("admin1Code"),
        country=loc.get("countryCode"),
    )

    attrs = [a.get("key") for a in (raw.get("attributes") or [])]
    job_types = list({_JOB_TYPES_BY_KEY[k] for k in attrs if k in _JOB_TYPES_BY_KEY})
    is_remote = _REMOTE_KEY in attrs

    comp = raw.get("compensation") or {}
    interval, min_amount, max_amount, currency = _parse_compensation(comp)

    employer = raw.get("employer") or {}
    dossier = employer.get("dossier") or {}
    employer_details = dossier.get("employerDetails") or {}
    images = dossier.get("images") or {}
    links = dossier.get("links") or {}
    ratings = ((employer.get("ugcStats") or {}).get("ratings") or {}).get("overallRating") or {}
    company_page = employer.get("relativeCompanyPageUrl")

    apply_url = (raw.get("recruit") or {}).get("viewJobUrl")
    from urllib.parse import urlsplit
    if apply_url and f".{urlsplit(apply_url).hostname}".endswith(".indeed.com"):
        apply_url = None

    addresses = employer_details.get("addresses") or []

    return JobDetail(
        site="indeed",
        job_url=f"{base_url}/viewjob?jk={job_key}",
        job_url_direct=apply_url,
        title=raw.get("title"),
        company=employer.get("name") or raw.get("sourceEmployerName"),
        company_url=f"{base_url}{company_page}" if company_page else None,
        company_url_direct=links.get("corporateWebsite"),
        company_logo=images.get("squareLogoUrl"),
        company_addresses=addresses[0] if addresses else None,
        company_industry=_clean_industry(employer_details.get("industry")),
        company_num_employees=employer_details.get("employeesLocalizedLabel"),
        company_revenue=employer_details.get("revenueLocalizedLabel"),
        company_description=employer_details.get("briefDescription"),
        company_rating=ratings.get("value"),
        company_reviews_count=ratings.get("count"),
        location=location,
        job_type=job_types or None,
        interval=interval,
        min_amount=min_amount,
        max_amount=max_amount,
        currency=currency,
        is_remote=is_remote,
        description=description,
        emails=emails,
    )


def _parse_compensation(comp: dict) -> tuple:
    """Retorna (interval, min_amount, max_amount, currency)."""
    currency = comp.get("currencyCode")

    for source in (comp, comp.get("estimated") or {}):
        sal = source.get("baseSalary")
        if not sal:
            continue
        r = sal.get("range") or {}
        low = r.get("min") or r.get("value")
        high = r.get("max") or r.get("value")
        if low or high:
            interval = parse_interval(sal.get("unitOfWork"))
            cur = source.get("currencyCode") or currency
            return interval, low, high, cur

    return None, None, None, currency


def _clean_industry(raw: str | None) -> str | None:
    if not raw:
        return None
    return raw.replace("Iv1", "").replace("_", " ").title().strip()
