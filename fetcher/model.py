from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel


class JobType(Enum):
    FULL_TIME = "fulltime"
    PART_TIME = "parttime"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    INTERNSHIP = "internship"
    PER_DIEM = "perdiem"
    OTHER = "other"
    VOLUNTEER = "volunteer"


class CompensationInterval(Enum):
    YEARLY = "yearly"
    MONTHLY = "monthly"
    WEEKLY = "weekly"
    DAILY = "daily"
    HOURLY = "hourly"


class Location(BaseModel):
    country: str | None = None
    city: str | None = None
    state: str | None = None

    def display(self) -> str:
        parts = [p for p in [self.city, self.state, self.country] if p]
        return ", ".join(parts)


class JobDetail(BaseModel):
    site: str
    job_url: str
    job_url_direct: str | None = None
    title: str | None = None
    company: str | None = None
    location: Location | None = None
    date_posted: date | None = None
    job_type: list[JobType] | None = None
    interval: CompensationInterval | None = None
    min_amount: float | None = None
    max_amount: float | None = None
    currency: str | None = None
    is_remote: bool | None = None
    job_level: str | None = None
    job_function: str | None = None
    description: str | None = None
    emails: list[str] | None = None
    company_industry: str | None = None
    company_url: str | None = None
    company_logo: str | None = None
    company_url_direct: str | None = None
    company_addresses: str | None = None
    company_num_employees: str | None = None
    company_revenue: str | None = None
    company_description: str | None = None
    company_rating: float | None = None
    company_reviews_count: int | None = None

    def to_dict(self) -> dict:
        d = self.model_dump()
        if self.location:
            d["location"] = self.location.display()
        if self.job_type:
            d["job_type"] = ", ".join(jt.value for jt in self.job_type)
        if self.interval:
            d["interval"] = self.interval.value
        return d
