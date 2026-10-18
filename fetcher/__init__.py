from __future__ import annotations

import time
from urllib.parse import urlparse

from fetcher import glassdoor, indeed, linkedin
from fetcher.model import JobDetail


def fetch_job(
    url: str,
    proxies: list[str] | None = None,
    ca_cert: str | None = None,
    user_agent: str | None = None,
    description_format: str = "markdown",
) -> JobDetail:
    """
    Recebe a URL de uma vaga e retorna seus dados completos incluindo descrição.

    Parâmetros
    ----------
    url:
        URL direta da vaga (LinkedIn, Indeed ou Glassdoor).
    proxies:
        Lista de proxies no formato ``['user:pass@host:port', 'localhost']``.
    ca_cert:
        Caminho para um certificado CA customizado.
    user_agent:
        Sobrescreve o user-agent padrão.
    description_format:
        ``'markdown'`` (padrão), ``'plain'`` ou ``'html'``.

    Retorna
    -------
    JobDetail
        Modelo Pydantic com todos os campos da vaga.
    """
    site = _detect_site(url)
    kwargs = dict(
        url=url,
        proxies=proxies,
        ca_cert=ca_cert,
        user_agent=user_agent,
        description_format=description_format,
    )
    if site == "linkedin":
        return linkedin.fetch(**kwargs)
    if site == "indeed":
        return indeed.fetch(**kwargs)
    if site == "glassdoor":
        return glassdoor.fetch(**kwargs)
    raise ValueError(
        f"Site não suportado: {urlparse(url).hostname}. "
        "Suportados: linkedin.com, indeed.com, glassdoor.com"
    )


def _detect_site(url: str) -> str:
    hostname = urlparse(url).hostname or ""
    if "linkedin.com" in hostname:
        return "linkedin"
    if "indeed.com" in hostname:
        return "indeed"
    if "glassdoor." in hostname:
        return "glassdoor"
    return hostname
