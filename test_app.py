import unittest
from app import normalize_probs, score_stock, classify

class TestEngine(unittest.TestCase):
    def test_probabilities(self):
        p=normalize_probs({'bull':2,'base':5,'bear':3})
        self.assertAlmostEqual(sum(p.values()),1.0)
        self.assertEqual(p['base'],.5)
    def test_classification(self):
        self.assertEqual(classify(75),'STUDY')
        self.assertEqual(classify(55),'WATCH')
        self.assertEqual(classify(30),'AVOID')
    def test_missing_data_is_neutral_not_best(self):
        s,parts=score_stock({'r20':None,'r60':None,'vol':None,'drawdown':None,'rel':None,'volume_ratio':None,'news':0})
        self.assertTrue(35 <= s <= 60)
        self.assertIn('fundamental',parts)
    def test_score_schema(self):
        s,p=score_stock({'r20':.1,'r60':.2,'vol':.2,'drawdown':-.1,'rel':.1,'volume_ratio':1.2,'news':1})
        self.assertTrue(0 <= s <= 100)
        self.assertEqual(set(p),{'trend','relative_strength','risk','liquidity','fundamental','news'})

if __name__=='__main__': unittest.main()
