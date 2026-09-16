"""Синтетичні приклади погоджених правил, не вимірювання точності."""
import hashlib
import sqlite3
import unittest
from copy import deepcopy
from pipeline.document_scope import admission
from pipeline.episode_rules import (RULES_VERSION, analyze_document, span, init_ledger,
                                    store_analysis, apply_case_change)

FACT = 'ОСОБА_1 вчинив крадіжку в магазині по вул. Тестова, 16.'
FINDING = 'Суд визнав доведеним цей епізод крадіжки ОСОБА_1.'
DISPOSITION = 'ОСОБА_1 визнати винуватим за ст. 185 КК.'
FINALITY = 'Вирок набрав законної сили 01.09.2026.'
TEXT = ('Проживає по вул. Інша, 9.\n' + FACT + '\n' + FINDING + '\n'
        + DISPOSITION + '\n' + FINALITY)
DOC = dict(doc_id='123', case_number='1/2/26', source_url='https://example.invalid/source',
           source_row_hash='a'*64, justice_kind='2', judgment_code='1',
           category_code='40576', instance_code='3')


def review(text=TEXT, outcome='conviction'):
    return dict(doc_id='123', source_row_hash='a'*64, text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                rules_version=RULES_VERSION, analyst='synthetic', reviewed_at='2026-09-16',
                episodes=[dict(episode_id='e1', subject='ОСОБА_1', outcome=outcome, court_accepted=True, scope_resolved=True,
                  evidence={k:span(text,q) for k,q in [('facts',FACT),('finding',FINDING),
                            ('disposition',DISPOSITION),('location',FACT)]},
                  location_link_checked=True, privacy_checked=True, location_privacy_checked=True,
                  geocode_verified=True, within_kyiv_verified=True,
                  finality={'status':'verified', 'verified_by':'synthetic',
                            'basis':'explicit_effective_statement','evidence':span(text,FINALITY)})])


class EpisodeRulesTests(unittest.TestCase):
    def test_store_not_residence_and_source_bound_repeat(self):
        a = analyze_document(DOC,TEXT,review())
        self.assertEqual(a['episodes'][0]['location']['street'], 'вул. Тестова')
        self.assertTrue(a['publication_allowed'])
        conn=sqlite3.connect(':memory:'); self.addCleanup(conn.close); init_ledger(conn)
        store_analysis(conn,a); store_analysis(conn,a)
        self.assertEqual(conn.execute('SELECT sum(count) FROM public_episode_counts').fetchone()[0],1)
        self.assertEqual(conn.execute('SELECT count(*) FROM episode_ledger').fetchone()[0],1)
        stale=review(); stale['text_sha256']='b'*64
        with self.assertRaises(ValueError): analyze_document(DOC,TEXT,stale)
        changed=deepcopy(a); changed['episodes']=[]; store_analysis(conn,changed)
        self.assertEqual(conn.execute('SELECT count(*) FROM episode_ledger').fetchone()[0],0)

    def test_no_header_or_active_status_proves_episode_or_finality(self):
        self.assertFalse(analyze_document(DOC,'ВСТАНОВИВ: '+TEXT)['publication_allowed'])
        r=review(); r['episodes'][0]['court_accepted']=False
        self.assertFalse(analyze_document(DOC,TEXT,r)['episodes'][0]['confirmed'])
        for finality in ({}, {'status':'verified','basis':'elapsed_time'},
                         {'status':'verified','basis':'no_appeal_found'}):
            r=review(); r['episodes'][0]['finality']=finality
            a=analyze_document(dict(DOC,status=1),TEXT,r)
            self.assertTrue(a['episodes'][0]['confirmed'])
            self.assertFalse(a['publication_allowed'])

    def test_acquittal_mixed_and_all_closures(self):
        for outcome in ['acquittal','no_event','no_elements','unproven','time_limit','death',
                        'amnesty','decriminalized','transfer','duplicate_decision','criminal_release',
                        'returned_materials','procedural','mixed_unresolved','minor_oral_remark']:
            a=analyze_document(DOC,TEXT,review(outcome=outcome))
            self.assertFalse(a['publication_allowed'],outcome)
        r=review(); e=deepcopy(r['episodes'][0]); e.update(episode_id='e2',outcome='acquittal')
        r['episodes'].append(e)
        a=analyze_document(DOC,TEXT,r)
        self.assertEqual([e['publication_allowed'] for e in a['episodes']],[True,False])

    def test_agreement_simplified_and_probation(self):
        for mode in ['agreement','simplified']:
            r=review(); r['episodes'][0]['procedure']=mode
            self.assertFalse(analyze_document(DOC,TEXT,r)['publication_allowed'])
            r['episodes'][0]['evidence']['charge_scope']=span(TEXT,FACT)
            self.assertTrue(analyze_document(DOC,TEXT,r)['publication_allowed'])
        text=TEXT+' Звільнити від відбування покарання з випробуванням.'
        self.assertTrue(analyze_document(DOC,text,review(text))['publication_allowed'])

    def test_refusal_separate_and_medical_police_address_not_event(self):
        facts='ОСОБА_1 керував по вул. Тестова, 16. Від проходження огляду відмовився.'
        finding='Суд визнав доведеною відмову ОСОБА_1 від огляду.'
        disposition='ОСОБА_1 визнати винним за ч. 1 ст. 130 КУпАП та накласти стягнення у виді штрафу.'
        text=facts+' '+finding+' '+disposition+' '+FINALITY
        doc=dict(DOC,justice_kind='5',judgment_code='2',category_code='41090')
        r=review(); r['text_sha256']=hashlib.sha256(text.encode()).hexdigest(); e=r['episodes'][0]
        e['outcome']='kupap_penalty'; e['subtype']='examination_refusal'
        e['evidence']={k:span(text,q) for k,q in [('facts',facts),('finding',finding),
                      ('disposition',disposition),('location',facts),('subtype','Від проходження огляду відмовився.')]}
        e['finality']['evidence']=span(text,FINALITY)
        a=analyze_document(doc,text,r)
        self.assertEqual(a['episodes'][0]['category'],'examination_refusal')
        self.assertTrue(a['episodes'][0]['confirmed'])
        e['subtype']='impaired_driving'
        self.assertFalse(analyze_document(doc,text,r)['publication_allowed'])
        for place in ['Медичний огляд проведено по вул. Лікарняна, 5.',
                      'Відділ поліції розташований по вул. Поліцейська, 7.']:
            t=TEXT+' '+place; r=review(t); r['episodes'][0]['evidence']['location']=span(t,place)
            a=analyze_document(DOC,t,r)
            self.assertIsNone(a['episodes'][0]['location'])
            self.assertFalse(a['publication_allowed'])

    def test_privacy_and_geography_cannot_be_assumed_from_court(self):
        for phrase in ['Участь неповнолітньої особи.', 'Домашнє насильство.',
                       'Примусові заходи медичного характеру.', 'Закрите судове засідання.']:
            t=TEXT+' '+phrase
            self.assertFalse(analyze_document(DOC,t,review(t))['publication_allowed'])
        r=review(); r['episodes'][0]['within_kyiv_verified']=False
        self.assertFalse(analyze_document(DOC,TEXT,r)['publication_allowed'])
        self.assertEqual(admission('4','2','41090'),'unsupported_document')
        self.assertEqual(admission('5','2','41237'),'privacy_excluded')
        self.assertEqual(admission('2','5','40576','2'),'review_only')
        self.assertEqual(admission('2','1','unknown'),'unknown_category')

    def test_appeal_revocation_counts_and_cassation_no_duplicate(self):
        conn=sqlite3.connect(':memory:'); self.addCleanup(conn.close); init_ledger(conn)
        a=analyze_document(DOC,TEXT,review()); store_analysis(conn,a)
        def change(doc,action):
            return dict(doc_id=doc,case_number=DOC['case_number'],source_url='https://example.invalid/appeal',
                        verified_by='synthetic',case_link_checked=True,action=action,
                        text_sha256=hashlib.sha256(TEXT.encode()).hexdigest(),evidence=span(TEXT,FINDING))
        for action in ['appeal_upheld','cassation_filed']:
            apply_case_change(conn,change(action,action),TEXT)
            self.assertEqual(conn.execute('SELECT sum(count) FROM public_episode_counts').fetchone()[0],1)
        c=change('appeal','cancelled'); apply_case_change(conn,c,TEXT); apply_case_change(conn,c,TEXT)
        self.assertEqual(conn.execute('SELECT count(*) FROM public_episode_counts').fetchone()[0],0)
        store_analysis(conn,a)
        self.assertEqual(conn.execute('SELECT count(*) FROM public_episode_counts').fetchone()[0],0)
        self.assertEqual(conn.execute('SELECT count(*) FROM episode_ledger').fetchone()[0],1)
