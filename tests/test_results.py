import unittest

from whoosh import analysis, fields, formats, qparser, query, searching
from whoosh.filedb.filestore import RamStorage


class TestResults(unittest.TestCase):
    def test_score_retrieval(self):
        schema = fields.Schema(title=fields.TEXT(stored=True),
                               content=fields.TEXT(stored=True))
        storage = RamStorage()
        ix = storage.create_index(schema)
        writer = ix.writer()
        writer.add_document(title=u"Miss Mary",
                            content=u"Mary had a little white lamb its fleece was white as snow")
        writer.add_document(title=u"Snow White",
                            content=u"Snow white lived in the forest with seven dwarfs")
        writer.commit()
        
        searcher = ix.searcher()
        results = searcher.search(query.Term("content", "white"))
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['title'], u"Miss Mary")
        self.assertEqual(results[1]['title'], u"Snow White")
        self.assertNotEqual(results.score(0), None)
        self.assertNotEqual(results.score(0), 0)
        self.assertNotEqual(results.score(0), 1)

    def test_resultcopy(self):
        schema = fields.Schema(a=fields.TEXT(stored=True))
        st = RamStorage()
        ix = st.create_index(schema)
        
        w = ix.writer()
        w.add_document(a=u"alfa bravo charlie")
        w.add_document(a=u"bravo charlie delta")
        w.add_document(a=u"charlie delta echo")
        w.add_document(a=u"delta echo foxtrot")
        w.commit()
        
        s = ix.searcher()
        r = s.search(qparser.QueryParser("a").parse(u"charlie"))
        self.assertEqual(len(r), 3)
        rcopy = r.copy()
        self.assertEqual(r.top_n, rcopy.top_n)
        self.assertEqual(r.scores, rcopy.scores)
        
    def test_resultslength(self):
        schema = fields.Schema(id=fields.ID(stored=True),
                               value=fields.TEXT)
        st = RamStorage()
        ix = st.create_index(schema)
        
        w = ix.writer()
        w.add_document(id=u"1", value=u"alfa alfa alfa alfa alfa")
        w.add_document(id=u"2", value=u"alfa alfa alfa alfa")
        w.add_document(id=u"3", value=u"alfa alfa alfa")
        w.add_document(id=u"4", value=u"alfa alfa")
        w.add_document(id=u"5", value=u"alfa")
        w.add_document(id=u"6", value=u"bravo")
        w.commit()
        
        s = ix.searcher()
        r = s.search(query.Term("value", u"alfa"), limit=3)
        self.assertEqual(len(r), 5)
        self.assertEqual(r.scored, 3)

    def test_pages(self):
        from whoosh.scoring import Frequency
        
        schema = fields.Schema(id=fields.ID(stored=True), c=fields.TEXT)
        st = RamStorage()
        ix = st.create_index(schema)
        
        w = ix.writer()
        w.add_document(id=u"1", c=u"alfa alfa alfa alfa alfa alfa")
        w.add_document(id=u"2", c=u"alfa alfa alfa alfa alfa")
        w.add_document(id=u"3", c=u"alfa alfa alfa alfa")
        w.add_document(id=u"4", c=u"alfa alfa alfa")
        w.add_document(id=u"5", c=u"alfa alfa")
        w.add_document(id=u"6", c=u"alfa")
        w.commit()
        
        s = ix.searcher(weighting=Frequency)
        q = query.Term("c", u"alfa")
        r = s.search(q)
        self.assertEqual([d["id"] for d in r], ["1", "2", "3", "4", "5", "6"])
        r = s.search_page(q, 2, pagelen=2)
        self.assertEqual([d["id"] for d in r], ["3", "4"])
        
        r = s.search_page(q, 2, pagelen=4)
        self.assertEqual(r.total, 6)
        self.assertEqual(r.pagenum, 2)
        self.assertEqual(r.pagelen, 2)
    
    def test_page_counts(self):
        from whoosh.scoring import Frequency
        
        schema = fields.Schema(id=fields.ID(stored=True))
        st = RamStorage()
        ix = st.create_index(schema)
        
        w = ix.writer()
        for i in xrange(10):
            w.add_document(id=unicode(i))
        w.commit()
        s = ix.searcher(weighting=Frequency)
        q = query.Every("id")
        
        r = s.search(q)
        self.assertEqual(len(r), 10)
        
        self.assertRaises(ValueError, s.search_page, q, 0)
        
        r = s.search_page(q, 1, 5)
        self.assertEqual(len(r), 10)
        self.assertEqual(r.pagecount, 2)
        
        r = s.search_page(q, 1, 5)
        self.assertEqual(len(r), 10)
        self.assertEqual(r.pagecount, 2)
        
        r = s.search_page(q, 2, 5)
        self.assertEqual(len(r), 10)
        self.assertEqual(r.pagecount, 2)
        self.assertEqual(r.pagenum, 2)
        
        r = s.search_page(q, 1, 10)
        self.assertEqual(len(r), 10)
        self.assertEqual(r.pagecount, 1)
        self.assertEqual(r.pagenum, 1)
    
    def test_keyterms(self):
        ana = analysis.StandardAnalyzer()
        vectorformat = formats.Frequency(ana)
        schema = fields.Schema(path=fields.ID,
                               content=fields.TEXT(analyzer=ana,
                                                   vector=vectorformat))
        st = RamStorage()
        ix = st.create_index(schema)
        w = ix.writer()
        w.add_document(path=u"a",content=u"This is some generic content")
        w.add_document(path=u"b",content=u"This is some distinctive content")
        w.commit()
        
        s = ix.searcher()
        docnum = s.document_number(path=u"b")
        keyterms = list(s.key_terms([docnum], "content"))
        self.assertTrue(len(keyterms) > 0)
        self.assertEqual(keyterms[0][0], "distinctive")
        
        r = s.search(query.Term("path", u"b"))
        keyterms2 = list(r.key_terms("content"))
        self.assertTrue(len(keyterms2) > 0)
        self.assertEqual(keyterms2[0][0], "distinctive")
        
    def test_facets(self):
        import random
        from collections import defaultdict
        
        schema = fields.Schema(id=fields.STORED, chapter=fields.ID)
        ix = RamStorage().create_index(schema)
        
        w = ix.writer()
        domain = u"alfa bravo charlie delta echo".split()
        targets = dict(zip(domain, (5, 10, 7, 2, 9)))
        cats = defaultdict(list)
        i = 0
        while targets:
            choice = random.choice(targets.keys())
            w.add_document(id=i, chapter=choice)
            cats[choice].append((i, 1.0))
            i += 1
            targets[choice] -= 1
            if targets[choice] == 0:
                del targets[choice]
        w.commit()
        
        s = ix.searcher()
        fs = searching.Facets(s)
        for name in domain:
            fs.add_facet(name, query.Term("chapter", name))
        
        r = s.search(query.Every("chapter"), limit=None)
        self.assertEqual(fs.counts(r), dict(alfa=5, bravo=10, charlie=7, delta=2, echo=9))
        self.assertEqual(fs.categorize(r), dict(cats))
        



if __name__ == '__main__':
    unittest.main()




        
    