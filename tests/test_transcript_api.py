"""
Tests for POST /api/transcript.

Offline tests run by default. Live YouTube calls are opt-in (network + YouTube may rate-limit).
"""

import os
import unittest

from app import app


class TranscriptAPITest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.ctx = app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_transcript_missing_video_id(self):
        r = self.client.post("/api/transcript", json={})
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.get_json() or {})

    def test_transcript_invalid_video_id(self):
        r = self.client.post("/api/transcript", json={"video_id": "not-an-id"})
        self.assertEqual(r.status_code, 400)
        body = r.get_json() or {}
        self.assertIn("error", body)

    @unittest.skipUnless(
        os.getenv("RUN_TRANSCRIPT_INTEGRATION") == "1",
        "Set RUN_TRANSCRIPT_INTEGRATION=1 to run live YouTube transcript fetch",
    )
    def test_transcript_integration_sample_video(self):
        """
        Example: https://www.youtube.com/watch?v=mpSE9Zl2j0g

        This video may only offer German auto-captions; use target_lang \"de\" if English fails.
        """
        r = self.client.post(
            "/api/transcript",
            json={
                "video_id": "https://www.youtube.com/watch?v=mpSE9Zl2j0g",
                "target_lang": "de",
            },
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        data = r.get_json() or {}
        self.assertIn("transcript", data)
        self.assertEqual(data.get("video_id"), "mpSE9Zl2j0g")
        self.assertGreater(len(data.get("transcript") or ""), 30)
        self.assertIn("video_title", data)


if __name__ == "__main__":
    unittest.main()
