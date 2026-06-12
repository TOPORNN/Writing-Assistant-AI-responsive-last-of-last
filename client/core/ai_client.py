import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency guard
    load_dotenv = None

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency guard
    OpenAI = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = "gpt-4.1-mini"


class AIClient:
    """OpenAI-backed text correction client with a local fallback."""

    def __init__(self, model=None, enabled=True, reload_environment=False):
        self.enabled = bool(enabled)
        self._load_environment(override=bool(reload_environment))
        self.model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.client = OpenAI(api_key=self.api_key, timeout=20.0) if self.enabled and self.api_key and OpenAI is not None else None
        self.last_error = ""

    @property
    def is_available(self):
        return self.client is not None

    @property
    def has_api_key(self):
        return bool(self.api_key)

    def correct_spelling(self, text):
        source_text = str(text or "")
        if not source_text.strip():
            return {"issues": "교정할 텍스트가 없습니다.", "corrected": ""}
        if not self.is_available:
            return self.fake_spell_check(source_text)

        system_prompt = (
            "너는 한국어 맞춤법과 문체를 교정하는 도우미다. "
            "원문의 의미와 문단 구조는 최대한 유지한다. "
            "반드시 JSON만 출력한다."
        )
        user_prompt = (
            "아래 텍스트의 맞춤법, 띄어쓰기, 어색한 표현을 자연스럽게 교정해줘.\n"
            "반환 형식: {\"issues\":\"수정 요약\", \"corrected\":\"교정된 전체 텍스트\"}\n\n"
            f"{source_text}"
        )
        try:
            content = self._chat_json(system_prompt, user_prompt)
            issues = str(content.get("issues", "") or "").strip()
            corrected = str(content.get("corrected", "") or "").strip()
            if not corrected:
                corrected = source_text
            return {
                "issues": issues or "AI 교정 결과입니다.",
                "corrected": corrected,
            }
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            fallback = self.fake_spell_check(source_text)
            fallback["issues"] = f"AI 호출 실패로 더미 교정을 사용했습니다.\n{self.last_error}"
            return fallback

    def summarize(self, text):
        source_text = str(text or "").strip()
        if not source_text:
            return "요약할 텍스트가 없습니다."
        if not self.is_available:
            return self.fake_summary(source_text)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "너는 한국어 글을 짧고 명확하게 요약하는 도우미다."},
                    {"role": "user", "content": f"다음 글을 3문장 이내로 요약해줘.\n\n{source_text}"},
                ],
                temperature=0.2,
            )
            return self._message_text(response) or self.fake_summary(source_text)
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return self.fake_summary(source_text)

    def recommend_title(self, text, summary=None):
        source_text = str(text or "").strip()
        summary_text = str(summary or "").strip()
        if not source_text:
            return ""
        if not self.is_available:
            return self.fake_title(source_text, summary_text)

        if not summary_text:
            summary_text = self.summarize(source_text)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "너는 한국어 글 제목을 짧고 자연스럽게 추천하는 도우미다. "
                            "제목 하나만 출력하고, 따옴표나 설명은 붙이지 않는다."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "아래 요약과 원문을 바탕으로 제목을 하나 추천해줘.\n"
                            "조건: 8~24자 정도, 과장하지 않기, 본문 핵심이 드러나기.\n\n"
                            f"[요약]\n{summary_text}\n\n[원문]\n{source_text}"
                        ),
                    },
                ],
                temperature=0.4,
            )
            return self._clean_title(self._message_text(response)) or self.fake_title(source_text, summary_text)
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return self.fake_title(source_text, summary_text)

    def change_tone(self, text, tone):
        source_text = str(text or "").strip()
        tone_name = str(tone or "").strip() or "자연스러운"
        tone_guide = self._tone_guide(tone_name)
        if not source_text:
            return ""
        if not self.is_available:
            return f"{source_text}\n\n[{tone_name} 문체 테스트 결과]"

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "너는 한국어 문체를 자연스럽게 바꾸는 도우미다. "
                            "원문의 의미, 사실관계, 고유명사, 문단 구조는 최대한 유지한다."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"아래 글을 '{tone_name}'로 바꿔줘.\n"
                            f"말투 지침: {tone_guide}\n"
                            "새 내용이나 설명은 덧붙이지 말고, 변환된 본문만 출력해줘.\n\n"
                            f"{source_text}"
                        ),
                    },
                ],
                temperature=0.3,
            )
            return self._message_text(response) or source_text
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return f"{source_text}\n\n[AI 호출 실패: {self.last_error}]"

    def _tone_guide(self, tone_name):
        guides = {
            "귀여운 말투": "밝고 아기자기하게, 부담스럽지 않은 귀여운 표현을 약간 사용한다.",
            "사랑스러운 말투": "따뜻하고 다정하게, 호감과 배려가 느껴지는 표현으로 바꾼다.",
            "무뚝뚝한 말투": "짧고 담백하게, 감정 표현을 줄이고 직설적으로 바꾼다.",
            "정중한 말투": "예의 있고 격식 있게, 업무나 공식 문맥에도 어울리게 바꾼다.",
            "신난 말투": "활기차고 긍정적으로, 에너지가 느껴지는 표현으로 바꾼다.",
            "기운없는 말투": "차분하고 힘이 빠진 듯한 톤으로, 과장된 감탄은 줄인다.",
        }
        return guides.get(tone_name, "자연스럽고 읽기 편한 말투로 바꾼다.")

    def fake_spell_check(self, text):
        source_text = str(text or "")
        return {
            "issues": "테스트용 더미 교정 결과입니다. OPENAI_API_KEY를 설정하면 AI 교정을 사용합니다.",
            "corrected": self._dummy_correct(source_text),
        }

    def fake_summary(self, text):
        source_text = str(text or "").strip()
        if not source_text:
            return "요약할 텍스트가 없습니다."
        first_line = source_text.splitlines()[0].strip()
        return f"{first_line[:80]}..."

    def fake_title(self, text, summary=None):
        source = str(summary or text or "").strip()
        lines = [line.strip(" -:,.!?") for line in source.splitlines() if line.strip()]
        title = lines[0] if lines else source
        title = " ".join(title.split())
        for marker in ("[요약 완료]", "[교정 완료]", "[문체 변경 완료]"):
            title = title.replace(marker, "")
        if len(title) > 24:
            title = title[:24].rstrip()
        return self._clean_title(title) or "추천 제목"

    def _clean_title(self, title):
        value = str(title or "").strip()
        value = value.strip("\"'“”‘’[]() ")
        value = value.replace("\r", " ").replace("\n", " ")
        value = " ".join(value.split())
        for prefix in ("제목:", "추천 제목:", "추천:", "Title:"):
            if value.startswith(prefix):
                value = value[len(prefix):].strip()
        return value[:40].strip()

    def _chat_json(self, system_prompt, user_prompt):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        raw_text = self._message_text(response)
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            parsed = {"issues": "AI 응답을 JSON으로 해석하지 못했습니다.", "corrected": raw_text}
        return parsed if isinstance(parsed, dict) else {"issues": "", "corrected": str(parsed)}

    def _message_text(self, response):
        try:
            return str(response.choices[0].message.content or "").strip()
        except Exception:
            return ""

    def _dummy_correct(self, text):
        corrected = str(text or "")
        replacements = {
            "안됀": "안 된",
            "안되": "안 돼",
            "됬": "됐",
            "되요": "돼요",
            "왠만": "웬만",
            "어의": "어이",
            "맞춤뻡": "맞춤법",
        }
        for wrong, right in replacements.items():
            corrected = corrected.replace(wrong, right)
        return corrected

    def _load_environment(self, override=False):
        if load_dotenv is None:
            self._load_windows_user_environment(override=override)
            return
        for env_path in (PROJECT_ROOT / ".env", PROJECT_ROOT / "server" / ".env"):
            if env_path.exists():
                load_dotenv(env_path, override=bool(override))
        self._load_windows_user_environment(override=override)

    def _load_windows_user_environment(self, override=False):
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                for name in ("OPENAI_API_KEY", "OPENAI_MODEL"):
                    try:
                        value, _ = winreg.QueryValueEx(key, name)
                    except OSError:
                        continue
                    value = str(value or "").strip()
                    if value and (override or not os.getenv(name)):
                        os.environ[name] = value
        except Exception:
            pass
