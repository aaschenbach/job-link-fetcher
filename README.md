# job-link-fetcher

Busca dados completos de uma vaga de emprego a partir de sua URL — título, empresa, localização, salário, descrição e mais.

Suporta **LinkedIn**, **Indeed** e **Glassdoor**.

---

## Uso rápido (sem instalar nada)

Requer [uv](https://docs.astral.sh/uv/). As dependências são instaladas automaticamente na primeira execução.

```bash
uv run fetch.py "https://www.linkedin.com/jobs/view/4473231257"
uv run fetch.py "https://br.indeed.com/?vjk=c0b60bcb1c85c782"
uv run fetch.py "https://www.glassdoor.com.br/partner/jobListing.htm?jobListingId=1010293129656"
```

---

## Uso como biblioteca

```python
from fetcher import fetch_job

job = fetch_job("https://www.linkedin.com/jobs/view/4473231257")

print(job.title)
print(job.company)
print(job.location.display())   # "São Paulo, SP, Brazil"
print(job.description)

# Converter tudo para dict
data = job.to_dict()
```

### Parâmetros de `fetch_job`

| Parâmetro | Tipo | Padrão | Descrição |
|---|---|---|---|
| `url` | `str` | — | URL da vaga |
| `proxies` | `list[str]` | `None` | Ex.: `["user:pass@host:port"]` |
| `ca_cert` | `str` | `None` | Caminho para certificado CA customizado |
| `user_agent` | `str` | `None` | Sobrescreve o user-agent padrão |
| `description_format` | `str` | `"markdown"` | `"markdown"`, `"plain"` ou `"html"` |

### Campos retornados (`JobDetail`)

| Campo | Tipo | Descrição |
|---|---|---|
| `site` | `str` | `"linkedin"`, `"indeed"` ou `"glassdoor"` |
| `job_url` | `str` | URL canônica da vaga |
| `job_url_direct` | `str` | URL direta para aplicação (quando disponível) |
| `title` | `str` | Título da vaga |
| `company` | `str` | Nome da empresa |
| `location` | `Location` | Cidade, estado e país |
| `date_posted` | `date` | Data de publicação |
| `job_type` | `list` | `fulltime`, `parttime`, `contract`, etc. |
| `interval` | `str` | `hourly`, `monthly`, `yearly`, etc. |
| `min_amount` | `float` | Salário mínimo |
| `max_amount` | `float` | Salário máximo |
| `currency` | `str` | Moeda do salário |
| `is_remote` | `bool` | Vaga remota |
| `job_level` | `str` | Nível de senioridade |
| `job_function` | `str` | Área de atuação |
| `description` | `str` | Descrição completa da vaga |
| `emails` | `list[str]` | E-mails encontrados na descrição |
| `company_url` | `str` | Perfil da empresa no job board |
| `company_url_direct` | `str` | Site oficial da empresa |
| `company_logo` | `str` | URL do logo |
| `company_industry` | `str` | Setor da empresa |
| `company_addresses` | `str` | Endereço da sede |
| `company_num_employees` | `str` | Número de funcionários |
| `company_revenue` | `str` | Faturamento |
| `company_description` | `str` | Descrição da empresa |
| `company_rating` | `float` | Avaliação da empresa |
| `company_reviews_count` | `int` | Número de avaliações |

---

## Instalação como dependência

```bash
pip install -e .
```

Ou adicione ao seu `pyproject.toml`:

```toml
[project]
dependencies = [
    "job-link-fetcher @ git+https://github.com/aaschenbach/job-link-fetcher.git",
]
```

---

## Estrutura

```
fetcher/
  __init__.py     # fetch_job() — ponto de entrada
  model.py        # JobDetail, Location e tipos (Pydantic)
  util.py         # Sessões HTTP, conversores HTML
  linkedin.py     # Scraper LinkedIn
  indeed.py       # Scraper Indeed (GraphQL API)
  glassdoor.py    # Scraper Glassdoor (GraphQL /graph)
fetch.py          # CLI para uso com uv run
test_fetch.py     # Testes de integração
```

---

## Sobre rate limiting

Os três sites bloqueiam requisições agressivas. Estratégias utilizadas:

- **LinkedIn** — `requests` com user-agent de browser desktop
- **Indeed** — `requests` com user-agent do app móvel oficial e headers da API interna
- **Glassdoor** — `curl_cffi` impersonando Chrome (fingerprint TLS), com inicialização de sessão antes do GraphQL

Para ambientes de produção ou alto volume, use o parâmetro `proxies`.

---

## Origem

Este projeto foi criado como um extrator de URL única, complementar ao **[JobSpy](https://github.com/speedyapply/JobSpy)** — biblioteca que busca vagas por termo e localização em múltiplos job boards simultaneamente. A lógica de sessão HTTP, headers e parsing GraphQL foi derivada do código do JobSpy.


## Integração com Headhunter V2

O projeto irmão `headhunter` consome `fetch_job(url, description_format="markdown")`
como dependência local editável. A integração usa fila persistente, intervalo
mínimo de 60 segundos por plataforma, cooldown após 403/429 e cache das capturas.
Não execute o teste de URLs em loop para retomar falhas do Google: use o cache.
As sessões HTTP aguardam pelo menos três segundos entre suas requisições e
`FetchHTTPError` expõe `status_code` e `retry_after` sem copiar respostas sensíveis.

Retornos Indeed e Glassdoor precisam conter o ID solicitado; LinkedIn confere
ID e rota da URL final. Hosts semelhantes, IDs ambíguos e URLs sem HTTPS são
rejeitados. O chamador deve validar também descrição, identificação e possíveis
bloqueios: uma resposta HTTP 200 por si só não comprova descrição válida.

Homologação real de 18/10/2026: as três URLs do uso rápido retornaram descrições
válidas; documentos Google foram criados e relidos, com IDs confirmados em uma
planilha exclusiva de homologação. Evidências e comandos em
`../headhunter/docs/integracao-descricoes.md`. Nenhuma coleta oficial nessa etapa.
