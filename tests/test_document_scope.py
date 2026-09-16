"""Перевірка довідників і відбору; жодних реальних текстів."""
import csv
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from collections import Counter
from pipeline.document_scope import CATEGORIES, validate_dictionaries
from pipeline.phase2_qa import select_sample


def dictionary_zip(path, justice5='Адмінправопорушення'):
    tables = {
        'justice_kinds.csv': ('justice_kind', [('2','Кримінальне'),('4','Адміністративне'),('5',justice5)]),
        'judgment_forms.csv': ('judgment_code', [('1','Вирок'),('2','Постанова')]),
        'instances.csv': ('instance_code', [('1','Касаційна'),('2','Апеляційна'),('3','Перша')]),
        'cause_categories.csv': ('category_code', [(k,v['source_name']) for k,v in CATEGORIES.items()]),
    }
    with zipfile.ZipFile(path,'w') as z:
        for name,(key,rows) in tables.items():
            out=io.StringIO(); w=csv.writer(out,delimiter='\t'); w.writerow([key,'name']); w.writerows(rows)
            z.writestr(name,out.getvalue())
        z.writestr('courts.csv','court_code\tname\tinstance_code\tregion_code\n2601\tСинтетичний\t3\t26\n')


class DocumentScopeTests(unittest.TestCase):
    def test_actual_dictionary_values_required_not_only_numbers(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'dictionary.zip'; dictionary_zip(p)
            self.assertEqual(validate_dictionaries(p)['2601']['instance_code'],'3')
            dictionary_zip(p,justice5='Адміністративне')
            with self.assertRaises(ValueError): validate_dictionaries(p)

    def test_balanced_blind_selection_unknown_privacy_and_related_case_exclusion(self):
        def row(i,kind,form,category,case=None):
            return SimpleNamespace(doc_id=str(i),court_code='2601',status=1,justice_kind=kind,
                                   judgment_code=form,category_code=category,cause_num=case or str(i))
        rows=[row(i,'2','1','40576') for i in range(10)] + [row(i,'5','2','41080') for i in range(10,20)]
        rows += [row(30,'5','2','41237'),row(31,'5','2','unknown'),row(32,'1','3','40576'),
                 row(33,'4','2','41080'),row(34,'2','1','40576',' 1 / 2 / 26 ')]
        audit=Counter()
        chosen=select_sample(rows,10,'blind',['1/2/26'],audit=audit,balanced=True)
        self.assertEqual(Counter(r.justice_kind for r in chosen),{'2':5,'5':5})
        self.assertFalse({'30','31','32','33','34'} & {r.doc_id for r in chosen})
        self.assertEqual(audit['unknown:unknown'],1)
        self.assertEqual([r.doc_id for r in chosen], [r.doc_id for r in select_sample(reversed(rows),10,'blind',['1/2/26'],balanced=True)])
