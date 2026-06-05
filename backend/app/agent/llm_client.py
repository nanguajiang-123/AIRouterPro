from __future__ import annotations

from typing import Optional

import httpx

from config import settings
from app.logger import log

_INTENT_SYSTEM_PROMPT = """You are a network intent classifier. Your job is to map a user's scenario description (gaming, video streaming, file download, VoIP call, etc.) into exactly one of two traffic types:

- streaming: high-bandwidth-sensitive traffic (video streaming, file download, bulk data transfer, large file upload/download, etc.). The bottleneck bandwidth requirement is the primary concern.
- voip: low-latency-sensitive traffic (gaming, voice/video call, real-time interaction, live streaming with low delay, etc.). End-to-end delay must be minimized.

Rules:
1. Return ONLY the single word "streaming" or "voip".
2. No explanation, no punctuation, no extra text.
3. When unsure, default to "streaming".

Examples:
  看视频 → streaming
  下载文件 → streaming
  打游戏 → voip
  视频通话 → voip
  4K video streaming → streaming
  online gaming → voip
  bulk file transfer → streaming
  video conferencing → voip
  live broadcast → streaming
  cloud gaming → voip
"""


def classify_intent(scenario: str) -> str:
    """调用 DeepSeek 将场景描述分类为 ``"streaming"`` 或 ``"voip"``。

    返回 ``"streaming"``（带宽敏感）或 ``"voip"``（延迟敏感）。
    异常或空输入时默认返回 ``"streaming"``。
    """
    if not scenario or not scenario.strip():
        log.debug("Empty scenario, defaulting to streaming")
        return "streaming"

    log.info("Classifying intent via LLM: {}", scenario)

    api_key = settings.deepsearch_api_key
    api_url = settings.deepsearch_url.rstrip("/") + "/chat/completions"

    if not api_key:
        log.warning("No DEEPSEARCH_API_KEY configured, using rule fallback")
        return _rule_fallback(scenario)

    try:
        with httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            resp = client.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": _INTENT_SYSTEM_PROMPT},
                        {"role": "user", "content": scenario},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 10,
                },
            )
            resp.raise_for_status()
            body = resp.json()
            raw = body["choices"][0]["message"]["content"].strip().lower()
            log.debug("LLM raw response: {}", raw)

            if raw in ("streaming", "voip"):
                return raw

            log.warning("Unexpected LLM response '{}', defaulting to streaming", raw)
            return "streaming"

    except Exception as e:
        log.warning("LLM call failed ({}), using rule fallback", e)
        return _rule_fallback(scenario)


def _rule_fallback(scenario: str) -> str:
    """LLM 不可用时的规则回退。"""
    s = scenario.lower()
    # 低延迟关键词 → voip
    if any(kw in s for kw in ("游戏", "gaming", "voip", "通话", "call", "实时",
                               "交互", "interactive", "live", "延迟", "latency",
                               "语音", "video call", "会议", "conferenc")):
        return "voip"
    # 默认 → streaming
    return "streaming"
