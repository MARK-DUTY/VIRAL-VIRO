from __future__ import annotations

import copy
import os
import unittest
from unittest.mock import patch

from pipeline import config, script_gen


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.headers = {}
        self.text = str(payload)

    def json(self) -> dict:
        return self._payload


class GroqJsonTests(unittest.TestCase):
    def test_deprecated_model_is_migrated(self) -> None:
        with patch.dict(os.environ, {"GROQ_MODEL": "llama-3.3-70b-versatile"}):
            self.assertEqual(config._get_groq_model(), "openai/gpt-oss-120b")

    def test_strict_schema_for_standard_script(self) -> None:
        response_format = script_gen._script_response_format(podcast=False)
        json_schema = response_format["json_schema"]
        scene = json_schema["schema"]["properties"]["scenes"]["items"]

        self.assertEqual(response_format["type"], "json_schema")
        self.assertTrue(json_schema["strict"])
        self.assertEqual(
            scene["required"], ["text", "image_prompt", "keyword"]
        )
        self.assertNotIn("speaker", scene["properties"])
        self.assertFalse(scene["additionalProperties"])

    def test_strict_schema_for_podcast_requires_speaker(self) -> None:
        response_format = script_gen._script_response_format(podcast=True)
        scene = response_format["json_schema"]["schema"]["properties"]["scenes"]["items"]

        self.assertIn("speaker", scene["required"])
        self.assertEqual(scene["properties"]["speaker"]["enum"], ["A", "B"])

    def test_json_validation_error_is_retried_automatically(self) -> None:
        sent_payloads: list[dict] = []
        responses = iter(
            [
                _FakeResponse(
                    400,
                    {
                        "error": {
                            "code": "json_validate_failed",
                            "message": "Failed to validate JSON",
                        }
                    },
                ),
                _FakeResponse(
                    200,
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": (
                                        '{"scenes":[{"text":"Hola",'
                                        '"image_prompt":"a friendly host",'
                                        '"keyword":"friendly host"}],'
                                        '"titles":["Titulo"],"hashtags":["viral"]}'
                                    )
                                }
                            }
                        ]
                    },
                ),
            ]
        )

        def fake_post(_url, *, json, headers, timeout):  # noqa: ANN001, ARG001
            sent_payloads.append(copy.deepcopy(json))
            return next(responses)

        with (
            patch.object(script_gen.settings, "groq_api_key", "gsk_test"),
            patch.object(script_gen.settings, "groq_model", "custom-json-model"),
            patch.object(script_gen.requests, "post", side_effect=fake_post) as post,
            patch.object(script_gen.time, "sleep"),
        ):
            result = script_gen._call_groq(
                [{"role": "system", "content": "Return JSON only"}]
            )

        self.assertEqual(post.call_count, 2)
        self.assertEqual(result["scenes"][0]["text"], "Hola")
        self.assertEqual(sent_payloads[0]["temperature"], 0.4)
        self.assertEqual(sent_payloads[1]["temperature"], 0.2)
        self.assertEqual(
            sent_payloads[0]["response_format"], {"type": "json_object"}
        )


if __name__ == "__main__":
    unittest.main()
