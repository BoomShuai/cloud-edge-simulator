import unittest

from cloud_edge.core import CollaborativeSimulator, Task, default_links, default_nodes
from cloud_edge.core import latency_greedy, privacy_aware, research_workload, summarize


class CollaborativeSimulatorTest(unittest.TestCase):
    def setUp(self):
        self.sim = CollaborativeSimulator(default_nodes(), default_links())

    def test_transfer_and_compute_make_cloud_not_always_best(self):
        task = Task("tiny-realtime-control", 20, 0.3, 0.1, 30, 3)
        decision = latency_greedy(self.sim, task)

        self.assertIn(decision.node.tier, {"device", "edge"})
        self.assertTrue(decision.deadline_met)

    def test_large_low_privacy_task_can_use_cloud(self):
        task = Task("large-llm-batch", 25000, 0.8, 0.2, 300, 1)
        decision = latency_greedy(self.sim, task)

        self.assertEqual(decision.node.tier, "cloud")
        self.assertTrue(decision.deadline_met)

    def test_privacy_aware_keeps_sensitive_tasks_off_cloud(self):
        sensitive = Task("sensitive-medical-frame", 600, 24.0, 2.0, 400, 5)
        decision = privacy_aware(self.sim, sensitive)

        self.assertNotEqual(decision.node.tier, "cloud")

    def test_summary_reports_expected_metrics(self):
        decisions = self.sim.run(research_workload(), privacy_aware)
        summary = summarize(decisions)

        self.assertEqual(summary["tasks"], 8)
        self.assertGreaterEqual(summary["deadline_hit_rate"], 0.0)
        self.assertLessEqual(summary["deadline_hit_rate"], 1.0)
        self.assertIn("placements", summary)


if __name__ == "__main__":
    unittest.main()
