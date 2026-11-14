import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from cloud_edge.core import *
from cloud_edge.cli import main,load_scenario


class ContractTests(unittest.TestCase):
    def test_units_have_independent_known_answer(self):
        task=Task('toy',10,1,2,3040,1)
        node=Node('toy-cloud','cloud',2,3,.1)
        sim=CollaborativeSimulator([node],[Link('device','cloud',10,8),Link('cloud','device',20,8)])
        latency,energy=sim.estimate(task,node)
        self.assertAlmostEqual(latency,3038)
        self.assertAlmostEqual(energy,1)

    def test_unknown_tiers_zero_bandwidth_and_nonfinite_are_rejected(self):
        for f in [lambda:Node('a','unknown',1,0,0),lambda:Link('device','edge',0,0),
                  lambda:Task('a',float('nan'),0,0,1,1),lambda:Task('a',1,0,0,1,True),lambda:Node('a','edge',True,0,0)]:
            with self.assertRaises(ValueError):f()

    def test_duplicate_nodes_and_incomplete_links_are_rejected(self):
        with self.assertRaises(ValueError):CollaborativeSimulator(default_nodes(),[])
        with self.assertRaises(ValueError):CollaborativeSimulator(default_nodes()+[default_nodes()[0]],default_links())

    def test_sensitive_work_never_falls_back_to_cloud_when_infeasible(self):
        task=Task('toy',1,0,0,.0001,5)
        sim=CollaborativeSimulator(default_nodes(),default_links())
        result=privacy_aware(sim,task)
        self.assertNotEqual(result.node.tier,'cloud')
        self.assertFalse(result.deadline_met)

    def test_no_allowed_node_is_explicit_error(self):
        node=Node('only-cloud','cloud',10,0,0)
        sim=CollaborativeSimulator([node],[Link('device','cloud',0,1),Link('cloud','device',0,1)])
        with self.assertRaises(ValueError):privacy_aware(sim,Task('toy',1,0,0,1,5))

    def test_deterministic_decisions_and_cli_roundtrip(self):
        with tempfile.TemporaryDirectory() as temporary,contextlib.redirect_stdout(io.StringIO()):
            root=Path(temporary)
            self.assertEqual(main(['scenario','--output',str(root/'scenario.json')]),0)
            self.assertEqual(main(['run','--input',str(root/'scenario.json'),'--output',str(root/'one')]),0)
            self.assertEqual(main(['run','--input',str(root/'scenario.json'),'--output',str(root/'two')]),0)
            self.assertEqual((root/'one/report.json').read_bytes(),(root/'two/report.json').read_bytes())
            data=json.loads((root/'one/report.json').read_text())
            self.assertEqual(len(data['results']),4)
            self.assertTrue((root/'one/summary.csv').exists())
            with contextlib.redirect_stderr(io.StringIO()):self.assertEqual(main(['demo','--output',str(root/'one')]),2)


if __name__=='__main__':unittest.main()
