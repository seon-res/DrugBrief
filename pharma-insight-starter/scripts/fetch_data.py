"""Refresh a bounded public-data snapshot for the Pharma Insight static dashboard.

Stdlib only: no API key required at the starter scale. This example is not a
complete approval or trial surveillance database.
"""
import json
import logging
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "data.json"
FDA_ENDPOINT = "https://api.fda.gov/drug/drugsfda.json"
TRIAL_ENDPOINT = "https://clinicaltrials.gov/api/v2/studies"
LOG = logging.getLogger("pharma-insight")


def get_json(base_url, params):
    full_url = base_url + "?" + urlencode(params)
    last_error = None
    for attempt in range(3):
        try:
            req = Request(full_url, headers={"User-Agent": "PharmaInsightStarter/1.0 (public data educational dashboard)", "Accept": "application/json"})
            with urlopen(req, timeout=35) as resp:
                return json.load(resp)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            last_error = exc
            LOG.warning("Request failed (attempt %d): %s", attempt + 1, exc)
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Public API unavailable: {last_error}")


def normalize_fda_application(row, oldest, today):
    application = str(row.get("application_number", "")).strip()
    # Exclude ANDA generics: not a complete catalog of novel molecules.
    if not (application.startswith("NDA") or application.startswith("BLA")):
        return None
    eligible = []
    for entry in row.get("submissions", []) or []:
        if entry.get("submission_type") != "ORIG" or entry.get("submission_status") != "AP":
            continue
        raw = str(entry.get("submission_status_date", ""))
        if not re.fullmatch(r"\d{8}", raw):
            continue
        try:
            approved = datetime.strptime(raw, "%Y%m%d").date()
        except ValueError:
            continue
        if oldest <= approved <= today:
            eligible.append(approved)
    if not eligible:
        return None
    approved = max(eligible)
    openfda = row.get("openfda") or {}
    branded = openfda.get("brand_name") or []
    if isinstance(branded, str):
        branded = [branded]
    products = row.get("products") or []
    names = [str(p.get("brand_name", "")).strip() for p in products if p.get("brand_name")]
    name = (branded[0] if branded else (names[0] if names else application))
    appl_number = re.sub(r"\D", "", application)
    return {
        "type": "fda", "id": application, "application_number": application,
        "title": name, "drug": name, "company": row.get("sponsor_name", "정보 없음"),
        "date": approved.isoformat(),
        "url": "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo=" + appl_number,
    }


def fetch_fda(today=None, max_records=40):
    today = today or datetime.now(timezone.utc).date()
    oldest = today - timedelta(days=365)
    query = (
        f"submissions.submission_status_date:[{oldest:%Y%m%d} TO {today:%Y%m%d}] "
        "AND submissions.submission_type:ORIG AND submissions.submission_status:AP"
    )
    rows = {}
    # IMPORTANT: openFDA searches at the application level. We re-check EACH
    # submission because a match in another element may cause false positives.
    for page in range(6):
        payload = get_json(FDA_ENDPOINT, {"search": query, "sort": "submissions.submission_status_date:desc", "limit": 100, "skip": page * 100})
        applications = payload.get("results", [])
        for app in applications:
            normalized = normalize_fda_application(app, oldest, today)
            if normalized and (normalized["id"] not in rows or normalized["date"] > rows[normalized["id"]]["date"]):
                rows[normalized["id"]] = normalized
        LOG.info("FDA page %d, matched records so far: %d", page + 1, len(rows))
        if len(applications) < 100:
            break
        # Page-limited sample, NOT an exhaustive annual FDA approval dataset.
    return sorted(rows.values(), key=lambda r: r["date"], reverse=True)[:max_records]


def normalize_trial(study):
    protocol = study.get("protocolSection") or {}
    ident = protocol.get("identificationModule") or {}
    status = protocol.get("statusModule") or {}
    design = protocol.get("designModule") or {}
    sponsor = protocol.get("sponsorCollaboratorsModule") or {}
    conditions = (protocol.get("conditionsModule") or {}).get("conditions") or []
    interventions = (protocol.get("armsInterventionsModule") or {}).get("interventions") or []
    pharma = [i.get("name", "") for i in interventions if i.get("type") in ("DRUG", "BIOLOGICAL") and i.get("name")]
    phases = [p for p in (design.get("phases") or []) if p in ("PHASE1", "PHASE2", "PHASE3")]
    nct = ident.get("nctId")
    last_updated = (status.get("lastUpdatePostDateStruct") or {}).get("date")
    if not nct or not last_updated or not pharma or not phases:
        return None
    return {
        "type": "trial", "id": nct, "title": ident.get("briefTitle") or nct,
        "drug": ", ".join(pharma[:2]), "company": (sponsor.get("leadSponsor") or {}).get("name", "정보 없음"),
        "condition": ", ".join(conditions[:2]), "status": status.get("overallStatus", "UNKNOWN"),
        "phases": phases, "date": last_updated,
        "url": "https://clinicaltrials.gov/study/" + nct,
    }


def fetch_trials(max_records=80):
    # Recent *posted updates*, not necessarily new trial registrations.
    query = {
        "format": "json", "pageSize": 300,
        "filter.advanced": "AREA[StudyType]INTERVENTIONAL AND AREA[LeadSponsorClass]INDUSTRY",
        "sort": "LastUpdatePostDate:desc",
    }
    payload = get_json(TRIAL_ENDPOINT, query)
    normalized = [normalize_trial(s) for s in payload.get("studies", [])]
    records = [r for r in normalized if r]
    records.sort(key=lambda r: r["date"], reverse=True)
    return records[:max_records]


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    errors = []
    datasets = {}
    succeeded = 0
    for key, loader, source in (
        ("fda", fetch_fda, "openFDA"),
        ("trials", fetch_trials, "ClinicalTrials.gov"),
    ):
        try:
            datasets[key] = loader()
            succeeded += 1
            LOG.info("Loaded %d %s records", len(datasets[key]), source)
        except Exception as exc:
            LOG.exception("Failed to load %s", source)
            datasets[key] = []
            errors.append(f"{source} 수집 실패 (다음 갱신 때 재시도)")
    if succeeded == 0:
        LOG.error("Both data providers failed. Preserve previously published version.")
        sys.exit(1)
    output = {"mode": "live", "updated_at": datetime.now(timezone.utc).isoformat(), "errors": errors, **datasets}
    OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    LOG.info("Saved site/data.json")


if __name__ == "__main__":
    main()
