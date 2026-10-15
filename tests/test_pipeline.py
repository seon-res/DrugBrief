import sys
import unittest
import json
import tempfile
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import update_data
from update_data import iso_ymd, norm_fda_record, norm_trial, norm_federal_register, rss_items

class PipelineTests(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(iso_ymd('20261014'),'2026-10-14')
        self.assertEqual(iso_ymd('2026-10-14'),'2026-10-14')
        self.assertEqual(iso_ymd('20261501'),'')
    def test_fda_filters_supplements_and_generics(self):
        base={'application_number':'NDA987654','sponsor_name':'Test','products':[{'brand_name':'Example','active_ingredients':[{'name':'ABC'}]}],
              'submissions':[{'submission_type':'SUPPL','submission_status':'AP','submission_status_date':'20261001','submission_number':'2'},
                             {'submission_type':'ORIG','submission_status':'AP','submission_status_date':'20260112','submission_number':'1'}]}
        self.assertEqual(norm_fda_record(base,'2026-10-01','2026-10-15'),[])
        data=norm_fda_record(base,'2026-01-01','2026-10-15')
        self.assertEqual(len(data),1)
        self.assertEqual(data[0]['date'],'2026-01-12')
        self.assertEqual(norm_fda_record({**base,'application_number':'ANDA987654'}),[])
    def test_approval_letter_link_only_approval(self):
        good='https://www.accessdata.fda.gov/drugsatfda_docs/appletter/2026/220290Orig1s000ltr.pdf'
        sub={'application_docs':[{'applications_doc_title':'Review', 'applications_doc_type':'Review', 'application_docs_url':'https://example.org/review.pdf'},
                                 {'applications_doc_title':'Approval Letter', 'applications_doc_type':'Letter', 'application_docs_url':good}]}
        self.assertEqual(update_data.original_letter_link(sub),good)
        self.assertEqual(update_data.original_letter_link({'application_docs':[sub['application_docs'][0]]}), '')

    def test_curated_breztri_requires_matching_application_and_date(self):
        note={'reason_ko':'신규 추진제 HFO-1234ze(E)를 사용한 제형',
              'source_url':'https://www.accessdata.fda.gov/drugsatfda_docs/appletter/2026/220290Orig1s000ltr.pdf',
              'verified_at':'2026-10-15'}
        notes={('NDA220290','2026-10-08'):note}
        with patch.object(update_data,'read_curated_notes',return_value=notes):
            row={'application':'NDA220290','date':'2026-10-08','id':'FDA-NDA220290-1','title':'BREZTRI AEROSPHERE'}
            update_data.enrich_approval_reasons([row],max_pdf=0)
            self.assertEqual(row['reason_status'],'verified')
            self.assertIn('HFO-1234ze(E)',row['approval_reason'])
            self.assertIn('/220290Orig1s000ltr.pdf',row['reason_source_url'])
            wrong={**row,'date':'2026-10-09'}
            wrong.pop('approval_reason',None)
            update_data.enrich_approval_reasons([wrong],max_pdf=0)
            self.assertEqual(wrong['reason_status'],'pending')

    def test_full_backfill_starts_in_2015_and_rescans_monthly(self):
        from datetime import date
        now=date(2026,10,15)
        self.assertEqual(update_data.approval_scan_start({},now),('2015-01-01',True))
        info={'fda_coverage':{'history_complete':True,'start_date':'2015-01-01','last_full_scan_date':'2026-10-14'}}
        start,full=update_data.approval_scan_start(info,now)
        self.assertEqual((start,full),('2026-04-18',False))
        older={'fda_coverage':{**info['fda_coverage'],'last_full_scan_date':'2026-09-01'}}
        self.assertEqual(update_data.approval_scan_start(older,now),('2015-01-01',True))

    def test_fda_fetch_is_not_capped_at_250(self):
        from datetime import datetime,timezone
        applications=[]
        for n in range(300):
            applications.append({'application_number':f'NDA{n+200000}',
              'products':[{'brand_name':f'Drug {n}'}],
              'submissions':[{'submission_type':'ORIG','submission_status':'AP',
                             'submission_status_date':'20261010','submission_number':'1'}]})
        def response(_url,params):
            return {'results':applications if 'NDA' in params['search'] else [],
                    'meta':{'results':{'total':300 if 'NDA' in params['search'] else 0}}}
        with patch.object(update_data,'api_json',side_effect=response):
            rows=update_data.fetch_approvals('2026-10-01',now=datetime(2026,10,15,tzinfo=timezone.utc))
        self.assertEqual(len(rows),300)


    def test_unreviewed_record_does_not_claim_letter_verified(self):
        row={'id':'FDA-NDA900900-1','application':'NDA900900','date':'2026-10-02',
             'classification':'Type 5','dosage_form':'TABLET','url':'https://www.accessdata.fda.gov/'}
        update_data.enrich_approval_reasons([row],max_pdf=0)
        self.assertEqual(row['reason_status'],'pending')
        self.assertIn('승인서 확인이 필요합니다',row['approval_reason'])
        self.assertNotIn('확인 완료',row['reason_basis'])

    def test_original_record_has_document_details(self):
        base={'application_number':'NDA220290','sponsor_name':'ASTRAZENECA',
              'products':[{'brand_name':'BREZTRI AEROSPHERE','dosage_form':'AEROSOL, METERED'}],
              'submissions':[{'submission_type':'ORIG','submission_status':'AP',
                              'submission_status_date':'20261008','submission_number':'1',
                              'application_docs':[{'applications_doc_title':'Approval Letter',
                                'applications_doc_type':'Letter','application_docs_url':'https://www.accessdata.fda.gov/letter.pdf'}]}]}
        row=norm_fda_record(base)[0]
        self.assertEqual(row['dosage_form'],'AEROSOL, METERED')
        self.assertEqual(row['approval_letter_url'],'https://www.accessdata.fda.gov/letter.pdf')

    def test_automated_purpose_not_mislabeled_as_verified(self):
        row={'id':'FDA-NDA900901-1','application':'NDA900901','date':'2026-10-04',
             'approval_letter_url':'https://www.accessdata.fda.gov/letter.pdf'}
        with patch.object(update_data,'extract_letter_purpose',return_value='This NDA provides for a new formulation.'):
            update_data.enrich_approval_reasons([row],max_pdf=1)
        self.assertEqual(row['reason_status'],'auto_extracted')
        self.assertIn('자동 추출',row['reason_basis'])

    def test_trials_only_drugs(self):
        raw={'protocolSection':{'identificationModule':{'nctId':'NCT12345678','briefTitle':'Research test'},
             'designModule':{'studyType':'INTERVENTIONAL','phases':['PHASE3']},
             'statusModule':{'overallStatus':'RECRUITING','studyLastUpdatePostDateStruct':{'date':'2026-10-01'}},
             'armsInterventionsModule':{'interventions':[{'type':'DRUG','name':'New Agent'}]},
             'sponsorCollaboratorsModule':{'leadSponsor':{'name':'Sponsor'}}}}
        row=norm_trial(raw)
        self.assertEqual(row['id'],'NCT12345678')
        self.assertEqual(row['phase'],'Phase 3')
        raw['protocolSection']['armsInterventionsModule']['interventions'][0]['type']='DEVICE'
        self.assertIsNone(norm_trial(raw))
    def test_regulations_no_unrelated_items(self):
        self.assertIsNone(norm_federal_register({'document_number':'x','title':'Food labeling','abstract':'Food packaging','publication_date':'2026-10-10'}))
        row=norm_federal_register({'document_number':'2026-123','title':'Drug manufacturing requirements','abstract':'New guidance','publication_date':'2026-10-10','html_url':'https://www.federalregister.gov/d/2026-123'})
        self.assertEqual(row['agency'],'FDA / Federal Register')
    def test_end_to_end_partial_source_failure(self):
        with tempfile.TemporaryDirectory() as scratch:
            data=Path(scratch)
            history=[{'id':'LEG-one','kind':'regulation','title':'Old document','agency':'식약처','date':'2026-10-14'}]
            (data/'regulations-archive.json').write_text(json.dumps(history))
            (data/'regulations-history.json').write_text(json.dumps(history))
            base=[{'id':'FDA-NDA123-1','date':'2026-10-14','approval_type':'NDA 원허가'}]
            with patch.object(update_data,'DATA',data), \
                 patch.object(update_data,'fetch_approvals',return_value=base), \
                 patch.object(update_data,'fetch_trials',side_effect=RuntimeError('temporary failure')), \
                 patch.object(update_data,'fetch_federal_register',return_value=[{'id':'FR-x','date':'2026-10-14'}]), \
                 patch.object(update_data,'fetch_ema',return_value=[{'id':'EMA-x','date':'2026-10-12'}]):
                update_data.run()
                summary=update_data.read_json('metadata.json',{})
                self.assertEqual(summary['sources']['fda']['state'],'ok')
                self.assertEqual(summary['sources']['trials']['state'],'error')
                self.assertEqual(len(update_data.read_json('approvals.json',[])),1)
                self.assertEqual(len(update_data.read_json('regulations.json',[])),3)
                with patch.object(update_data,'fetch_approvals',side_effect=RuntimeError('rate limit')):
                    update_data.run()
                    self.assertEqual(update_data.read_json('metadata.json',{})['sources']['fda']['state'],'stale')
                    self.assertEqual(len(update_data.read_json('approvals.json',[])),1)

    def test_rss(self):
        xml=b'<rss><channel><item><title>Regulatory guidance</title><link>https://example.org/info</link><pubDate>Wed, 14 Oct 2026 09:00:00 GMT</pubDate></item></channel></rss>'
        rows=rss_items(xml,'EMA guidance')
        self.assertEqual(rows[0]['date'],'2026-10-14')

if __name__=='__main__':unittest.main()
