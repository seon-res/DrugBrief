#!/usr/bin/env python3
"""DrugBrief static data pipeline. Standard library only.

Every external record is linked to its source. Failing sources keep their last
successful snapshot and record a visible stale/error status in metadata.json.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / 'data'
UTC = timezone.utc
KST = timezone(timedelta(hours=9))
UA = 'DrugBrief-Research-Dashboard/1.0 (public regulatory data; educational use)'
FDA_API = 'https://api.fda.gov/drug/drugsfda.json'
CT_API = 'https://clinicaltrials.gov/api/v2/studies'
FR_API = 'https://www.federalregister.gov/api/v1/documents.json'
EMA_FEEDS = [
    ('EMA 규제·절차 가이드라인', 'https://www.ema.europa.eu/en/regulatory-and-procedural-guideline.xml'),
    ('EMA 과학 가이드라인', 'https://www.ema.europa.eu/en/scientific-guidelines.xml'),
]
NOTES = BASE / 'curated' / 'approval-notes.json'
REGULATORY_WORDS = ('drug','pharmaceutical','biologic','biosimilar','clinical trial','gmp','cgmp','guidance',
                    'medicinal','manufactur','drug labeling','medication labeling','drug application','drug approval','pharmacovigilance',
                    '의약품','바이오','임상','허가','가이드라인','규제','실사','제조','약물')


def iso_ymd(v):
    """Parse YYYYMMDD or ISO YYYY-MM-DD; return date string or ''."""
    v = str(v or '').strip()
    if re.fullmatch(r'\d{8}', v):
        try: return datetime.strptime(v, '%Y%m%d').date().isoformat()
        except ValueError: return ''
    if re.match(r'^\d{4}-\d{2}-\d{2}', v):
        try: return datetime.strptime(v[:10], '%Y-%m-%d').date().isoformat()
        except ValueError: return ''
    return ''


def now_iso():
    return datetime.now(KST).isoformat(timespec='seconds')


def write_json(name, obj):
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = DATA / (name+'.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
    tmp.replace(DATA / name)


def read_json(name, default):
    try: return json.loads((DATA/name).read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError): return default


def http_get(url, params=None, timeout=25, attempts=3):
    target = url + ('?' + urlencode(params, doseq=True) if params else '')
    last = None
    for retry in range(attempts):
        try:
            req = Request(target, headers={'User-Agent': UA, 'Accept': 'application/json, application/xml, application/rss+xml, */*'})
            with urlopen(req, timeout=timeout) as r:
                return r.read()
        except (HTTPError, URLError, TimeoutError, OSError) as err:
            last = err
            if isinstance(err, HTTPError) and err.code in (400, 401, 403, 404, 422): break
            if retry+1 < attempts: time.sleep(1.5*(retry+1))
    raise RuntimeError(f'HTTP error for {url}: {last}') from last


def api_json(url, params=None):
    return json.loads(http_get(url, params))


def good_url(value):
    return str(value or '') if str(value or '').startswith(('https://', 'http://')) else ''



def original_letter_link(submission):
    """Return *only* an FDA original submission's approval letter, if discoverable.

    OpenFDA sometimes lists multiple document types; a random document must not
    be described as an approval letter.
    """
    for doc in submission.get('application_docs') or []:
        if not isinstance(doc, dict):
            continue
        name = str(doc.get('applications_doc_title') or '')
        typ = str(doc.get('applications_doc_type') or '')
        link = good_url(doc.get('application_docs_url'))
        # A Letter PDF on an approved original submission is generally the
        # approval letter, but the document title must say Approval.
        if 'approval' in (name + ' ' + typ).lower() and 'letter' in (name + ' ' + typ).lower() and link:
            return link
    return ''


def approval_reason_fallback(record):
    """Structured facts, not an inferred scientific/regulatory rationale."""
    cls = str(record.get('classification') or '').strip()
    form = str(record.get('dosage_form') or '').strip()
    details = []
    if cls:
        details.append(f'FDA 제출 분류: {cls}')
    if form:
        details.append(f'허가 제품 제형: {form}')
    return '. '.join(details) + ('. ' if details else '') + '구체적인 승인 대상·변경 내용은 FDA 원허가 승인서 확인이 필요합니다.'


def read_curated_notes():
    try:
        raw = json.loads(NOTES.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    notes = {}
    for row in raw if isinstance(raw, list) else []:
        if not isinstance(row, dict):
            continue
        app = str(row.get('application') or '').upper().replace(' ', '')
        date = iso_ymd(row.get('date'))
        reason = str(row.get('reason_ko') or '').strip()
        source = good_url(row.get('source_url'))
        if re.fullmatch(r'(NDA|BLA)\d+', app) and date and reason and source:
            notes[(app, date)] = row
    return notes


def apply_curated_reason(row, notes):
    key = (str(row.get('application') or '').upper(), iso_ymd(row.get('date')))
    note = notes.get(key)
    if not note:
        return False
    row['approval_reason'] = str(note['reason_ko'])
    row['reason_status'] = 'verified'
    row['reason_basis'] = 'FDA 원허가 승인서 원문 확인'
    row['reason_source_url'] = good_url(note['source_url'])
    row['reason_verified_at'] = iso_ymd(note.get('verified_at'))
    row['reason_category'] = str(note.get('category') or '')
    if not row.get('approval_letter_url'):
        row['approval_letter_url'] = row['reason_source_url']
    return True


def extract_letter_purpose(pdf_url):
    """Conservative, non-AI extract from an official PDF, in English only.

    This is explicitly tagged *automatic*, not 'FDA letter manually reviewed'.
    No inferred Korean translation is produced from arbitrary letters.
    """
    host = (urlparse(pdf_url).hostname or '').lower()
    if host != 'www.accessdata.fda.gov' or not urlparse(pdf_url).path.lower().endswith('.pdf'):
        return ''
    try:
        from pypdf import PdfReader
    except ImportError:
        return ''
    try:
        blob = http_get(pdf_url, timeout=12, attempts=1)
        if len(blob) > 8_000_000 or not blob.startswith(b'%PDF'):
            return ''
        reader = PdfReader(BytesIO(blob), strict=False)
        text = ' '.join((page.extract_text() or '') for page in reader.pages[:2])
        text = re.sub(r'\s+', ' ', text)
        match = re.search(r'\bThis\s+(?:NDA|BLA)\s+provides\s+for\s+(.{30,800}?)'
                          r'(?=\s+(?:APPROVAL\s*(?:&|AND)\s*LABELING|APPROVAL\s+AND\s+LABELING|'
                          r'We\s+have\s+completed\s+our\s+review|CONTENT\s+OF\s+LABELING))',
                          text, re.I)
        if not match:
            return ''
        purpose = re.sub(r'\s+', ' ', match.group(1)).strip(' .;:')
        # No content, too-long passages or unhelpful boilerplate rejected.
        if len(purpose) > 650 or len(purpose) < 35:
            return ''
        return match.group(0).split(purpose)[0].strip() + ' ' + purpose + '.'
    except Exception as exc:
        print('WARN letter text unavailable:', str(exc)[:130], file=sys.stderr)
        return ''


def enrich_approval_reasons(rows, previous=None, max_pdf=12):
    """Curated FDA-backed notes > previous exact-date explanations > auto extract > pending.

    Never mark an automatically parsed letter as human verified.
    """
    notes = read_curated_notes()
    before = {x.get('id'): x for x in (previous or []) if x.get('id')}
    attempted = 0
    for row in rows:
        if not row.get('application', '').startswith(('NDA', 'BLA')):
            continue
        if apply_curated_reason(row, notes):
            continue
        old = before.get(row.get('id')) or {}
        if (old.get('date') == row.get('date') and
                old.get('reason_status') in ('verified', 'auto_extracted') and
                old.get('approval_reason') and old.get('reason_source_url')):
            for field in ('approval_reason','reason_status','reason_basis','reason_source_url',
                          'reason_verified_at','reason_category'):
                if field in old:
                    row[field] = old[field]
            if not row.get('approval_letter_url'):
                row['approval_letter_url'] = old.get('approval_letter_url') or ''
            continue
        letter = row.get('approval_letter_url')
        if letter and attempted < max_pdf:
            attempted += 1
            excerpt = extract_letter_purpose(letter)
            if excerpt:
                row.update({'approval_reason':excerpt,'reason_status':'auto_extracted',
                            'reason_basis':'FDA 승인서 영문 문구 자동 추출 · 해석 검토 필요',
                            'reason_source_url':letter})
                continue
        row.update({'approval_reason':approval_reason_fallback(row),
                    'reason_status':'pending','reason_basis':'FDA 구조화 데이터 · 승인서 미검토',
                    'reason_source_url':letter or row.get('url','')})
    return rows


def norm_fda_record(record, start='', end=''):
    """Return only NDA/BLA original approvals, not ANDA or supplements.
    Date range checked at submission level (API search matches parent application).
    """
    app = str(record.get('application_number') or '').upper().strip()
    if not app.startswith(('NDA', 'BLA')): return []
    products = record.get('products') or []
    openfda = record.get('openfda') or {}
    names = sorted({str(p.get('brand_name') or '').strip() for p in products if p.get('brand_name')})
    name = ', '.join(names[:3]) or ', '.join(openfda.get('brand_name') or []) or app
    ingredients = sorted({str(a.get('name') or '').strip() for p in products for a in (p.get('active_ingredients') or []) if a.get('name')})
    sponsor = str(record.get('sponsor_name') or '').strip()
    forms = sorted({str(p.get('dosage_form') or '').strip() for p in products if p.get('dosage_form')})
    rows=[]
    for sub in record.get('submissions') or []:
        if str(sub.get('submission_type') or '').upper() != 'ORIG': continue
        if str(sub.get('submission_status') or '').upper() != 'AP': continue
        approved = iso_ymd(sub.get('submission_status_date'))
        if not approved or (start and approved < start) or (end and approved > end): continue
        number = str(sub.get('submission_number') or '1')
        appl_no = ''.join(x for x in app if x.isdigit())
        rows.append({
            'id': 'FDA-' + app + '-' + number,
            'kind': 'approval','agency':'FDA', 'title': name,
            'subtitle': ' / '.join(ingredients[:4]) or '성분명 미기재',
            'company': sponsor, 'date': approved, 'application': app,
            'approval_type': 'BLA 원허가' if app.startswith('BLA') else 'NDA 원허가',
            'classification': str(sub.get('submission_class_code_description') or '').strip(),
            'dosage_form': ', '.join(forms[:3]),
            'approval_letter_url': original_letter_link(sub),
            'status': '승인',
            'description': f'FDA {app} original submission 승인 기록입니다. 적응증과 신규 유효성분 여부는 원문에서 별도로 확인하세요.',
            'url': f'https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={appl_no}' if appl_no else 'https://www.accessdata.fda.gov/scripts/cder/daf/',
            'date_basis': 'FDA submission status date',
            'source':'openFDA Drugs@FDA',
        })
    return rows


def fetch_approvals(days=240, now=None):
    today = (now or datetime.now(UTC)).date()
    begin = today - timedelta(days=days)
    found = {}
    # Limit cross-nested application matches by splitting into ~60-day windows and NDA/BLA groups.
    for prefix in ('NDA', 'BLA'):
        window_end = today
        while window_end >= begin:
            window_start = max(begin, window_end - timedelta(days=59))
            query = (f'application_number:{prefix}* AND submissions.submission_type:ORIG '
                     f'AND submissions.submission_status:AP AND submissions.submission_status_date:'
                     f'[{window_start:%Y%m%d} TO {window_end:%Y%m%d}]')
            limit, skip = 500, 0
            while skip <= 4500:
                try:
                    payload = api_json(FDA_API, {'search': query, 'limit': limit, 'skip': skip})
                except RuntimeError as err:
                    if isinstance(err.__cause__, HTTPError) and err.__cause__.code == 404:
                        break  # openFDA uses HTTP 404 for zero matching applications
                    raise
                entries = payload.get('results') or []
                for record in entries:
                    for item in norm_fda_record(record, window_start.isoformat(), window_end.isoformat()):
                        found[item['id']] = item
                total = (payload.get('meta') or {}).get('results',{}).get('total',0)
                if not entries or skip+len(entries) >= total: break
                skip += len(entries)
                time.sleep(.15)
            window_end = window_start - timedelta(days=1)
    if not found: raise RuntimeError('조회 기간 내 NDA/BLA 원허가 데이터를 찾지 못했습니다. FDA API 응답 조건을 확인하세요.')
    return sorted(found.values(), key=lambda a:(a['date'],a['id']), reverse=True)[:250]


def norm_trial(study):
    p = study.get('protocolSection') or {}
    iden, status, design = [p.get(k) or {} for k in ('identificationModule','statusModule','designModule')]
    sponsor = (p.get('sponsorCollaboratorsModule') or {}).get('leadSponsor') or {}
    conditions = (p.get('conditionsModule') or {}).get('conditions') or []
    intervention = (p.get('armsInterventionsModule') or {}).get('interventions') or []
    types = [str(x.get('type') or '').upper() for x in intervention]
    if not any(x in ('DRUG','BIOLOGICAL') for x in types): return None
    if str(design.get('studyType','INTERVENTIONAL')).upper() != 'INTERVENTIONAL': return None
    nct=str(iden.get('nctId') or '')
    if not re.fullmatch(r'NCT\d{8}',nct): return None
    last_submit=iso_ymd(((status.get('studyFirstPostDateStruct') or {}).get('date')))
    updated=iso_ymd(((status.get('studyLastUpdatePostDateStruct') or {}).get('date')))
    phase = ', '.join((design.get('phases') or [])) or '해당없음'
    enrollment = (design.get('enrollmentInfo') or {}).get('count')
    names = list(dict.fromkeys(str(i.get('name') or '') for i in intervention if i.get('name')))
    return {
        'id':nct,'kind':'trial','agency':'ClinicalTrials.gov',
        'title': str(iden.get('briefTitle') or nct),
        'subtitle':', '.join(conditions[:4]), 'company':str(sponsor.get('name') or ''),
        'date':updated or last_submit, 'first_posted':last_submit,
        'phase':phase.replace('EARLY_PHASE1','Early Phase 1').replace('PHASE','Phase '),
        'status':str(status.get('overallStatus') or 'UNKNOWN'),
        'interventions':names[:6], 'enrollment':enrollment,
        'start_date':iso_ymd((status.get('startDateStruct') or {}).get('date')),
        'description':'임상시험 등록정보이며 연구 성공 또는 의약품 승인을 의미하지 않습니다.',
        'url':'https://clinicaltrials.gov/study/'+nct,
        'source':'ClinicalTrials.gov', 'date_basis':'LastUpdatePostDate',
    }


def fetch_trials(target=200):
    found = {}
    params={'format':'json', 'pageSize':100, 'sort':'LastUpdatePostDate:desc',
            'filter.advanced':'AREA[StudyType]INTERVENTIONAL'}
    token=None
    for _ in range(8):
        req=dict(params)
        if token: req['pageToken'] = token
        payload = api_json(CT_API, req)
        for study in payload.get('studies') or []:
            item=norm_trial(study)
            if item: found[item['id']]=item
        if len(found) >= target: break
        token=payload.get('nextPageToken')
        if not token: break
    if not found: raise RuntimeError('ClinicalTrials.gov에서 의약품·생물학적 제제 중재시험을 찾지 못했습니다.')
    return sorted(found.values(), key=lambda a:(a['date'],a['id']), reverse=True)[:target]


class _Text(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]
    def handle_data(self, data): self.parts.append(data)


def plain_html(value):
    parser=_Text()
    parser.feed(str(value or ''))
    return re.sub(r'\s+',' ',' '.join(parser.parts)).strip()


def norm_federal_register(raw):
    ident=str(raw.get('document_number') or '')
    title=str(raw.get('title') or '').strip()
    if not ident or not title: return None
    type_code=str(raw.get('type') or '')
    sub=str(raw.get('abstract') or '').strip()
    if not any(w in (title+' '+sub).lower() for w in REGULATORY_WORDS): return None
    pub=iso_ymd(raw.get('publication_date'))
    return {'id':'FR-'+ident,'kind':'regulation','agency':'FDA / Federal Register',
            'title':title,'subtitle':sub[:550], 'company':'', 'date':pub,
            'reg_type':{'Rule':'최종 규칙','Proposed Rule':'규칙안','Notice':'공고'}.get(type_code,type_code or '규제 문서'),
            'description':sub[:800] or '공식 연방관보 문서입니다. 변경 내용 및 시행일은 원문에서 확인하세요.',
            'status':'공식 발표','url':good_url(raw.get('html_url')),
            'source':'Federal Register API', 'date_basis':'publication_date', 'is_historical':False}


def fetch_federal_register():
    q={'conditions[agencies][]':'food-and-drug-administration','per_page':100,'order':'newest'}
    doc=api_json(FR_API, q)
    items = [norm_federal_register(x) for x in (doc.get('results') or [])]
    return [x for x in items if x][:100]


def xml_local(tag):
    return tag.split('}')[-1].lower()


def rss_items(data, label):
    root = ET.fromstring(data)
    outputs=[]
    for entry in root.iter():
        if xml_local(entry.tag) not in ('item','entry'):continue
        props={}
        for child in entry:
            tag=xml_local(child.tag)
            if tag in ('title','link','description','summary','pubdate','published','updated','guid'):
                if tag=='link' and child.get('href'): props[tag]=child.get('href')
                elif child.text: props[tag]=child.text.strip()
        title=plain_html(props.get('title'))
        link=good_url(props.get('link') or props.get('guid'))
        if not title or not link: continue
        dt=''
        raw = props.get('pubdate') or props.get('published') or props.get('updated') or ''
        try: dt=parsedate_to_datetime(raw).date().isoformat()
        except (TypeError, ValueError, IndexError):dt=iso_ymd(raw)
        descript=plain_html(props.get('description') or props.get('summary'))[:750]
        outputs.append({'id':'EMA-'+hashlib.sha1(link.encode()).hexdigest()[:16],
                        'kind':'regulation','agency':'EMA','title':title,'subtitle':descript,
                        'company':'','date':dt,'reg_type':label, 'status':'공식 발표',
                        'description':descript or 'EMA 공식 가이드라인 자료입니다. 원문을 확인하세요.',
                        'url':link,'source':'EMA RSS','date_basis':'RSS 게시일','is_historical':False})
    return outputs


def fetch_ema():
    out=[]
    failures=[]
    for label,url in EMA_FEEDS:
        try: out+=rss_items(http_get(url),label)
        except Exception as e: failures.append(str(e))
    if not out: raise RuntimeError('EMA RSS 전체 실패: '+('; '.join(failures)[:360]))
    if failures: print('WARN EMA 일부 피드 실패: '+'; '.join(failures),file=sys.stderr)
    return out


def current_snapshot(name, current, item_cap):
    # Merge new and previous records; keep last successful history to avoid blinking on subsequent runs.
    before=read_json(name, [])
    byid={str(it.get('id')):it for it in before if it.get('id')}
    byid.update({str(it['id']):it for it in current if it.get('id')})
    out=sorted(byid.values(),key=lambda x:(x.get('date') or '',x.get('id') or ''),reverse=True)[:item_cap]
    write_json(name,out)
    return out


def run():
    DATA.mkdir(parents=True,exist_ok=True)
    info=read_json('metadata.json',{})
    previous=info.get('sources') or {}
    status={}
    counts={}
    started=now_iso()
    jobs = [
        ('fda','approvals.json',lambda:fetch_approvals(),250),
        ('trials','trials.json',lambda:fetch_trials(),300),
        ('federal_register','regulations-live-fda.json',fetch_federal_register,250),
        ('ema','regulations-live-ema.json',fetch_ema,250),
    ]
    for key,name,func,cap in jobs:
        print('FETCH',key, flush=True)
        old=read_json(name,[])
        try:
            fresh=func()
            if not fresh: raise RuntimeError('API returned no matching records')
            if key == 'fda':
                fresh = enrich_approval_reasons(fresh, previous=old)
            merged=current_snapshot(name,fresh,cap)
            status[key]={'state':'ok','last_success':started,'message':'수집 성공','count':len(fresh)}
            counts[key]=len(merged)
            print('OK',key, 'new',len(fresh),'total',len(merged),flush=True)
        except Exception as e:
            if key == 'fda' and old:
                enrich_approval_reasons(old, previous=old, max_pdf=0)
                write_json(name, old)
            error = str(e)[:450]
            old_success=(previous.get(key) or {}).get('last_success')
            status[key]={'state':'stale' if old else 'error','last_success':old_success,
                         'message':error,'count':len(old)}
            counts[key]=len(old)
            print('WARN',key,error,'retained',len(old),file=sys.stderr,flush=True)
    # Live + official historical regulatory archive. Clearly label historical source dates.
    live=read_json('regulations-live-fda.json',[])+read_json('regulations-live-ema.json',[])
    archive=read_json('regulations-archive.json',[])
    seen={}
    for item in archive+live:
        k=str(item.get('id') or item.get('url'))
        if k:seen[k]=item
    merged=sorted(seen.values(),key=lambda x:(x.get('date') or '',x.get('id') or ''),reverse=True)
    write_json('regulations.json',merged[:1700])
    info.update({'updated_at':started,'sources':status,'counts':counts,
                 'regulations_shown':len(merged[:1700]),'historic_total':len(read_json('regulations-history.json',[])),
                 'note':'규제 역사 자료는 제공된 원본 ZIP의 2026-10-15 스냅샷을 기반으로 합니다. 일부 최신 정보는 외부 API 상태에 따라 지연될 수 있습니다.'})
    write_json('metadata.json',info)
    print('FINISHED status=',{k:v['state'] for k,v in status.items()},flush=True)
    if all(s['state']=='error' for s in status.values()):
        print('WARNING: 모든 실시간 데이터 소스 실패. 빈 데이터/과거 스냅샷을 명확히 표시하여 배포합니다.', file=sys.stderr)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',action='store_true',help='Fetch and update online sources')
    args=parser.parse_args()
    if args.run:run()
    else:parser.print_help()
