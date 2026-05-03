import json
import unittest

from deep_research.server import _sse


class ServerTest(unittest.TestCase):
    def test_sse_frame_contains_event_and_json_payload(self):
        frame = _sse("stage", {"stage": "queued", "message": "ok"}).decode("utf-8")

        self.assertIn("event: stage", frame)
        data_line = next(line for line in frame.splitlines() if line.startswith("data: "))
        self.assertEqual(json.loads(data_line.removeprefix("data: "))["stage"], "queued")


if __name__ == "__main__":
    unittest.main()
