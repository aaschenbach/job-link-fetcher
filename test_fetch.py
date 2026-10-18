"""
Testes de integração: busca dados reais das URLs fornecidas.
Execute com:  python test_fetch.py
"""
from __future__ import annotations

import time
import sys
from fetcher import fetch_job

URLS = [
    (
        "Glassdoor",
        "https://www.glassdoor.com.br/partner/jobListing.htm?pos=101&ao=1110586&s=224"
        "&guid=000001a14497c652a1eca3339a32e516&src=GD_JOB_AD&t=JA&vt=e"
        "&uido=7C00CAD561C4AF068BC9B3B4C264C376&ea=1&cs=1_582d5145"
        "&cb=1792152899675&jobListingId=1010293129656"
        "&cpc=983919718F9DC6F6"
        "&jrtk=5-yul1-0-1k52a63svi9fr802-a8f0ac22ec15da3c---6NYlbfkN0DX9ElKqD93P_544fiTBS-XThqn_8iehWPP_1QJNrDEtoqSm9R4IfuUjpCODvbPcaPLhFERmhgEneKC-iVBIASeqJ1hIw6HeM4iZJ35zT2O5If0R8Fd2GcIv_wcqvaXATvDSkVJsqxF9sxKTHFi5gbOFb5o6r7R6ObYnCT3JpuHhJK9AcE0Lh5wLtiHW-Ez847LdVqPTvWJpUZy_kMBsMdUOtptkIhTUDUOzZdqj8x7GfKM61QJ0IIIBXTdfr0apDGYMdDqegI0j9n1NA4Zg4O5qg0nkMATMUzr2DWlIZgFYEqRrDbo1Ve_pVnnVaic6Fw6QwlIBT60Az1FPaF_cxG8hTgizIfe7zobRACptV9FsVHGl3ukMUcu_I9yBjyBuVruvhSEtSth9EQ5yWxWs8NWBYUM6cO7hHtbE3ONmdTAp_5BViOMz5Vx_dlDNL1GU9rS3Bkm4JJYEsR3-4LOnLH7etoB3naGbIGex6Pmfng3DjFT_ISqLvlw6UPWWCJ_4LxUqg0kgdugdJAQRvuuM0wtyQDFBKzoN3JtYOTQqc7rVNHYY320lSBUP70khNRNBUl-7CNuz-uMP5D1Bpg6dBrWh_KD2-aToPgXPq9lj6p_2H_7yGRumg4R6OEPjnlqeMLy0k8Q_TulqVfnYZYYVL3TCcIVijm7UcyQAXX46dCgr8Nr-tIFi97WJVBkLwqQaSCqJYamTOEKRFtZSQNvDtPgBjm95Nu9lgKZsdPfpiH7qTEeflrZ-n9zLfhEtG1i7-CXz-Q1r2LCik6wx6ZZen3isGnOmcGv9xGfQfUaGXuqTYzdRU6lx0ublq16vaAu9T--jyRKuu-PDffjnEEnKqBs78g0n-tCf5k1c2jMiF6HGyKpZh_YvOEiLBTx8M0z6o2t4PoR_tjSWBcVEo8xLG12TqtL0ZBOE80AEQqfH-MlR9jFg3fnbH8VAfKykxP80sgfZ2Xz5T0-ab-RmF-4tRrDkj5DNqI5HYrYsiRyK_roZ1y7iFtl_3R68vw4diGKJEJhlYwDFZqNSw-mXY6HdGUVAszypUgHJAHxYs5I5vHFiTfWQxB-GxLBysBNRZWmQ2Dg_mnOBdBrC3bsNyDPWaKLfv2sDUcVOrMk2dbSzxnds-LpQb6fWGL86wDRDSPEItaDuUaPbDu35Bcds0YxCZ0yU227WwIYDzg%3D"
        "&tgt=GD_JOB_VIEW&utm_medium=email&utm_source=jobalert&utm_campaign=jobAlertAlert"
        "&utm_content=ja-jobpos1-age3d-1010293129656&ja=402867911",
    ),
    (
        "LinkedIn",
        "https://www.linkedin.com/comm/jobs/view/4473231257/"
        "?trackingId=efUaLtti51CulysYeMTHeg%3D%3D"
        "&refId=JeO%2FlzZAz1wnjBLQ7giU2w%3D%3D"
        "&lipi=urn%3Ali%3Apage%3Aemail_email_jobs_facet_suggestions%3BgKI%2BEWcOTcCiltsx9loXMQ%3D%3D"
        "&midToken=AQEICee4_FslQw&midSig=36vh76nYO7Ncs1"
        "&trk=eml-email_jobs_facet_suggestions-JOBS_POSTING_SECTION-0-view_job"
        "&trkEmail=eml-email_jobs_facet_suggestions-JOBS_POSTING_SECTION-0-view_job-null-2p7ye~mvawqafi~im-null-null"
        "&eid=2p7ye-mvawqafi-im"
        "&otpToken=ZTExYWEyOWYxYTgwZjM2YTQ5OWQxM2RmODI3M2IxYzhmN2I1YmY0MTQzNjg5YWMyYzhiMGQyODVmMzdhYzgzMzg2ZDc1MGI4ZmZjZWU2OWYyNmE4MjYyOWZlNmQ1YmZiMzI4ZTllOGU3NjVkMjIxOWU1NjBiZjA2OThhNjVjNWRkMGE0NjMsMiwx",
    ),
    (
        "Indeed",
        "https://br.indeed.com/?vjk=c0b60bcb1c85c782",
    ),
]


def print_job(label: str, job) -> None:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    d = job.to_dict()
    for key, value in d.items():
        if value is None:
            continue
        if key == "description":
            snippet = str(value)[:300].replace("\n", " ")
            print(f"  {key}: {snippet}...")
        else:
            print(f"  {key}: {value}")


errors = []
for label, url in URLS:
    print(f"\n→ Buscando {label}...")
    try:
        job = fetch_job(url, description_format="markdown")
        print_job(label, job)
    except Exception as e:
        print(f"  ERRO: {e}")
        errors.append((label, str(e)))
    time.sleep(3)

if errors:
    print(f"\n\n{'='*60}")
    print("ERROS:")
    for label, msg in errors:
        print(f"  {label}: {msg}")
    sys.exit(1)
else:
    print("\n\nTodos os testes passaram.")
