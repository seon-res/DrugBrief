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
