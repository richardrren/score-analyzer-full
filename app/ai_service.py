from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .models import StudentAnalysis


@dataclass
class AIConfig:
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = ""
    timeout: int = 60

    @property
    def enabled(self) -> bool:
        return bool(self.api_key.strip() and self.base_url.strip() and self.model.strip())


def _is_chat_completions_endpoint(base_url: str) -> bool:
    base = base_url.strip().rstrip("/")
    return base.endswith("/chat/completions")


def _build_payload(config: AIConfig, prompt: str) -> Dict[str, Any]:
    model = config.model.strip()
    if _is_chat_completions_endpoint(config.base_url):
        return {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }
    return {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            }
        ],
    }


def _endpoint(base_url: str) -> str:
    base = base_url.strip().rstrip("/")
    if base.endswith("/responses"):
        return base
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/responses"


def _analysis_payload(analysis: StudentAnalysis) -> Dict[str, Any]:
    return {
        "name": analysis.name,
        "total": analysis.total_display,
        "score_rate": round(analysis.score_rate, 4),
        "weak_concepts": [{"name": s.name, "rate": round(s.rate, 4)} for s in analysis.weaknesses],
        "strong_concepts": [{"name": s.name, "rate": round(s.rate, 4)} for s in analysis.strengths],
        "weak_questions": [
            {
                "number": wq.question.number,
                "type": wq.question.question_type,
                "concept": wq.question.core_concept,
                "earned": wq.earned,
                "score": wq.question.score,
                "difficulty": wq.question.difficulty,
                "misconception": wq.question.misconception,
            }
            for wq in analysis.weak_questions[:8]
        ],
    }


def generate_ai_summary(config: AIConfig, analysis: StudentAnalysis) -> str:
    if not config.enabled:
        raise RuntimeError("未配置 OpenAI 兼容接口")

    prompt = (
        "你是一名初中科学教师。请根据 JSON 数据，为学生生成一段中文个性化分析建议。"
        "要求：不改写客观分数；先概括表现，再指出 2-3 个薄弱点，最后给出可执行复习建议；"
        "控制在 180 字以内。JSON："
        + json.dumps(_analysis_payload(analysis), ensure_ascii=False)
    )
    body = _build_payload(config, prompt)
    request = urllib.request.Request(
        _endpoint(config.base_url),
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key.strip()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=max(config.timeout, 5)) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"AI 接口返回错误：HTTP {exc.code} {detail[:200]}") from exc
    except Exception as exc:
        raise RuntimeError(f"AI 调用失败：{exc}") from exc

    text = _extract_text(data)
    if not text:
        raise RuntimeError("AI 响应中没有可用文本")
    return text.strip()


def _extract_text(data: Dict[str, Any]) -> Optional[str]:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    parts: list[str] = []
    for output in data.get("output", []) or []:
        for content in output.get("content", []) or []:
            if isinstance(content.get("text"), str):
                parts.append(content["text"])
    if parts:
        return "\n".join(parts)
    choices = data.get("choices") or []
    if choices:
        message = choices[0].get("message", {})
        if isinstance(message.get("content"), str):
            return message["content"]
    return None
