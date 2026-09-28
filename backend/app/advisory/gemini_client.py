"""Gemini 3.7 Flash Advisory Client.

Wrapper for Google Gemini API. Isolated from prompt text definitions.
Calls Gemini once per high-risk district summary (not per individual data point).
Includes in-memory response caching and resilient fallback generation.
"""

import json
from typing import Dict, List, Optional
import httpx
from pydantic import ValidationError

from app.advisory.prompts import (
    DistrictAdvisoryResult,
    DistrictRiskSummaryInput,
    MockedDispatch,
    SYSTEM_PROMPT_TEMPLATE,
    build_fallback_advisory,
    format_district_advisory_prompt,
)


class GeminiAdvisoryClient:
    """Client for generating district-level early-warning advisories via Gemini."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-3.7-flash",
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        # In-memory cache key: (storm_name, step_index, district)
        self._cache: Dict[str, DistrictAdvisoryResult] = {}

    def _cache_key(self, data: DistrictRiskSummaryInput) -> str:
        return f"{data.storm_name}_{data.step_index}_{data.district}"

    async def generate_district_advisory(
        self,
        summary_input: DistrictRiskSummaryInput,
    ) -> DistrictAdvisoryResult:
        """Call Gemini 3.7 Flash with structured district risk metrics.

        Returns structured advisory content and mocked SMS/email dispatch.
        Falls back to deterministic advisory if network or quota errors occur.
        """
        cache_k = self._cache_key(summary_input)
        if cache_k in self._cache:
            return self._cache[cache_k]

        if not self.api_key:
            fallback = build_fallback_advisory(summary_input)
            self._cache[cache_k] = fallback
            return fallback

        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_name}:generateContent?key={self.api_key}"
        )

        user_prompt = format_district_advisory_prompt(summary_input)
        payload = {
            "systemInstruction": {
                "parts": [{"text": SYSTEM_PROMPT_TEMPLATE}]
            },
            "contents": [
                {
                    "parts": [{"text": user_prompt}]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2,
                "maxOutputTokens": 800,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(endpoint, json=payload)
                if res.status_code == 200:
                    body = res.json()
                    candidates = body.get("candidates", [])
                    if candidates:
                        text_part = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        parsed_json = json.loads(text_part)

                        # Validate against schema
                        result = DistrictAdvisoryResult(
                            district=parsed_json.get("district", summary_input.district),
                            state=parsed_json.get("state", summary_input.state),
                            risk_level=parsed_json.get("risk_level", "HIGH"),
                            headline=parsed_json.get("headline", f"Cyclone Advisory for {summary_input.district}"),
                            key_risks=parsed_json.get("key_risks", []),
                            recommended_actions=parsed_json.get("recommended_actions", []),
                            mocked_dispatch=MockedDispatch(
                                sms_preview=parsed_json.get("mocked_dispatch", {}).get("sms_preview", ""),
                                email_preview=parsed_json.get("mocked_dispatch", {}).get("email_preview", ""),
                            ),
                        )
                        self._cache[cache_k] = result
                        return result
        except Exception:
            # Fallback on timeout or JSON parse issue
            pass

        fallback = build_fallback_advisory(summary_input)
        self._cache[cache_k] = fallback
        return fallback

    async def generate_batch_advisories(
        self,
        district_summaries: List[DistrictRiskSummaryInput],
    ) -> List[DistrictAdvisoryResult]:
        """Generate advisories for top-N highest-risk districts in a timestep."""
        results: List[DistrictAdvisoryResult] = []
        for dist in district_summaries:
            advisory = await self.generate_district_advisory(dist)
            results.append(advisory)
        return results
