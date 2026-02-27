from openai import OpenAI
from app.utils.config import Config


class AIClient:
    def __init__(self, config: Config = None):
        self._config = config or Config()
        self._client = None
        self._init_client()

    def _init_client(self):
        api_key = self._config.get("ai.api_key", "")
        base_url = self._config.get("ai.base_url", "https://api.openai.com/v1")
        if api_key:
            self._client = OpenAI(api_key=api_key, base_url=base_url)

    def update_config(self, config: Config):
        self._config = config
        self._init_client()

    @property
    def is_configured(self):
        return self._client is not None

    def chat(self, messages: list, **kwargs) -> str:
        if not self._client:
            raise RuntimeError("AI 未配置，请先设置 API Key")
        model = kwargs.pop("model", None) or self._config.get("ai.model", "gpt-4o")
        max_tokens = kwargs.pop("max_tokens", None) or self._config.get("ai.max_tokens", 2000)
        temperature = kwargs.pop("temperature", None) or self._config.get("ai.temperature", 0.7)
        resp = self._client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )
        return resp.choices[0].message.content

    def chat_stream(self, messages: list, **kwargs):
        if not self._client:
            raise RuntimeError("AI 未配置，请先设置 API Key")
        model = kwargs.pop("model", None) or self._config.get("ai.model", "gpt-4o")
        max_tokens = kwargs.pop("max_tokens", None) or self._config.get("ai.max_tokens", 2000)
        temperature = kwargs.pop("temperature", None) or self._config.get("ai.temperature", 0.7)
        stream = self._client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
            **kwargs,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
