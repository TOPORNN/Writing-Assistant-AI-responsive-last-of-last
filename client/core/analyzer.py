from client.core.ai_client import AIClient


class TextAnalyzer:
    """UI-facing analyzer facade.

    The UI calls this class only. OpenAI-specific details stay inside AIClient so
    API prompts, models, and fallback behavior can change without rewriting UI.
    """

    TEMP_SPELLING_FEEDBACK = "AI 또는 더미 교정 결과입니다."
    TEMP_RESULT_MARKERS = {
        "spelling": "[교정 완료]",
        "summary": "[요약 완료]",
        "tone": "[문체 변경 완료]",
    }

    def __init__(self, api_enabled=True):
        self.ai = AIClient(enabled=api_enabled)
        self._spelling_cache = {}

    def reload_api(self, api_enabled=True):
        self.ai = AIClient(enabled=api_enabled, reload_environment=True)
        self._spelling_cache.clear()
        return self.ai

    def analyze_spelling(self, text):
        result = self.check_spelling(text)
        return self.format_spell_check(result)

    def analyze_summary(self, text):
        result = self.summarize(text)
        return self.format_summary(result)

    def analyze_evaluation(self, text):
        return "100점\n\n테스트용 평가 결과입니다."

    def analyze_title_recommendation(self, text):
        source_text = str(text or "").strip()
        if not source_text:
            return ""
        summary = self.ai.summarize(source_text)
        return self.ai.recommend_title(source_text, summary)

    def analyze_tone_change(self, text, tone):
        return self.ai.change_tone(text, tone)

    def check_spelling(self, text):
        source_text = str(text or "")
        if source_text in self._spelling_cache:
            return self._spelling_cache[source_text]

        result = self.ai.correct_spelling(source_text)
        self._spelling_cache[source_text] = result
        if len(self._spelling_cache) > 80:
            first_key = next(iter(self._spelling_cache))
            self._spelling_cache.pop(first_key, None)
        return result

    def summarize(self, text):
        return self.ai.summarize(text)

    def format_spell_check(self, result):
        issues = ""
        corrected = ""

        if isinstance(result, dict):
            issues = result.get("issues", "")
            corrected = result.get("corrected", "")
        else:
            corrected = str(result)

        sections = ["맞춤법 교정 결과:"]
        if issues.strip():
            sections.extend(["", issues.strip()])

        sections.extend(["", "교정문:", "", self._append_temp_marker(corrected, "spelling")])
        return "\n".join(sections).rstrip()

    def format_summary(self, result):
        summary_text = self._append_temp_marker(result, "summary")
        return f"요약 결과:\n\n{summary_text}"

    def _append_temp_marker(self, text, feature_name):
        value = str(text or "").strip()
        marker = self.TEMP_RESULT_MARKERS[feature_name]
        if value.endswith(marker):
            return value
        return f"{value}\n\n{marker}".strip()
