import unittest

from deep_research.models import Stage
from deep_research.pipeline import DeepResearchPipeline


class DeepResearchPipelineTest(unittest.TestCase):
    def test_pipeline_runs_medical_neuroscience_scenario(self):
        events = []
        pipeline = DeepResearchPipeline(on_event=events.append)

        bundle = pipeline.run("의료 신경과학 공부하는 방법")

        self.assertEqual(bundle.question.intent, "learning_plan")
        self.assertEqual(bundle.question.domain, "medical_neuroscience")
        self.assertIn("의료 신경과학", bundle.answer)
        self.assertTrue(bundle.evidence)
        self.assertTrue(bundle.ranked_sources)
        self.assertEqual(events[0].stage, Stage.QUEUED)
        self.assertEqual(events[-1].stage, Stage.COMPLETED)

    def test_pipeline_generates_follow_up_queries_for_gaps(self):
        pipeline = DeepResearchPipeline()

        bundle = pipeline.run("의료 신경과학 공부하는 방법")

        self.assertTrue(bundle.follow_up_queries)
        self.assertTrue(any("목차 공백" in query.purpose for query in bundle.follow_up_queries))

    def test_source_ids_are_unique_across_initial_and_follow_up_searches(self):
        pipeline = DeepResearchPipeline()

        bundle = pipeline.run("의료 신경과학 공부하는 방법")
        source_ids = [source.result.source_id for source in bundle.ranked_sources]

        self.assertEqual(len(source_ids), len(set(source_ids)))

    def test_source_urls_are_deduplicated_across_searches(self):
        pipeline = DeepResearchPipeline()

        bundle = pipeline.run("의료 신경과학 공부하는 방법")
        urls = [source.result.url for source in bundle.ranked_sources]

        self.assertEqual(len(urls), len(set(urls)))

    def test_bundle_includes_execution_cautions(self):
        pipeline = DeepResearchPipeline()

        bundle = pipeline.run("의료 신경과학 공부하는 방법")

        self.assertTrue(bundle.cautions)
        self.assertTrue(any("rate limit" in caution for caution in bundle.cautions))


if __name__ == "__main__":
    unittest.main()
