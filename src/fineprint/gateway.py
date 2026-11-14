import logging
import time
from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4

import openai
from openai import OpenAI, omit
from pydantic import BaseModel, SecretStr, ValidationError

from fineprint.settings import settings

logger = logging.getLogger(__name__)

ProviderName = Literal["opencode_go", "openrouter", "azure_foundry", "amazon_bedrock"]


class ProviderConfig(BaseModel):
    name: ProviderName
    api_key: SecretStr | None
    base_url: str | None
    model_name: str | None
    temperature: float | None = 0.1
    timeout: int = 120
    headers: dict | None = None
    extra_body: dict | None = None


def provider_configed(provider: ProviderConfig) -> bool:
    return None not in (provider.model_name, provider.api_key, provider.base_url)


providers: list[ProviderConfig] = [
    ProviderConfig(
        name="azure_foundry",
        base_url=settings.foundry_endpoint,
        api_key=settings.foundry_api_key,
        model_name=settings.foundry_model,
        temperature=None,
    ),
    ProviderConfig(
        name="opencode_go",
        base_url=settings.opencode_endpoint,
        api_key=settings.opencode_api_key,
        model_name=settings.opencode_model,
        headers={
            "User-Agent": "fineprint-engine/0.1",
            "x-opencode-session": str(uuid4()),
        },
    ),
    ProviderConfig(
        name="openrouter",
        base_url=settings.openrouter_endpoint,
        api_key=settings.openrouter_api_key,
        model_name=settings.openrouter_model,
        extra_body={"provider": {"require_parameters": True}},
    ),
]

configed_providers = [
    provider for provider in providers if provider_configed(provider) == True
]


class ProviderFailure(Exception):
    """One provider couldn't answer this request. The next provider may still work."""

    def __init__(self, provider: ProviderName, reason: str, detail: str = ""):
        super().__init__(f"{provider}: {reason}")
        self.provider = provider
        self.reason = reason
        self.detail = detail


class AllProvidersFailed(Exception):
    def __init__(self, failures: list[ProviderFailure]):
        super().__init__("all providers failed: " + "; ".join(str(f) for f in failures))
        self.failures = failures


@dataclass
class GatewayResult:
    parsed: BaseModel  # the answer, already validated against the schema
    content: str  # the raw JSON text the model returned
    provider: ProviderName
    model: str  # what the provider says answered, e.g. "gpt-5-mini-2025-08-07"
    temperature: float | None  # what was sent; None means it wasn't sent
    seconds: float
    failed_before: list[str] = field(default_factory=list)  # e.g. ["azure_foundry: timeout"]


def _reason(error: openai.APIError) -> str:
    # order matters: APITimeoutError is a subclass of APIConnectionError
    if isinstance(error, openai.APITimeoutError):
        return "timeout"
    if isinstance(error, openai.APIConnectionError):
        return "connection"
    if isinstance(error, openai.APIStatusError):
        return f"http {error.status_code} {type(error).__name__}"
    return type(error).__name__


class LLMGateway:
    def __init__(self):
        self._clients: dict[ProviderName, OpenAI] = {}

    def get_client(self, provider: ProviderConfig) -> OpenAI:
        # one client per provider, reused: a client keeps its HTTP connections open,
        # so a warm Lambda doesn't redo the TLS handshake for every question
        if provider.name not in self._clients:
            self._clients[provider.name] = OpenAI(
                base_url=provider.base_url,
                # the one place the real key leaves SecretStr; passing the SecretStr itself
                # sends "Bearer **********" and every call gets a 401
                api_key=provider.api_key.get_secret_value(),
                max_retries=1,  # the SDK retries timeouts, 429 and 5xx once before raising
                default_headers=provider.headers if provider.headers else omit,
            )
        return self._clients[provider.name]

    def ask_llm(
        self,
        messages: list[dict],
        schema: type[BaseModel],
        pin: ProviderName | None = None,
    ) -> GatewayResult:
        """Try the configured providers in order and return the first valid answer.

        pin: use only this provider, no fallback. Eval runs pin, so one run never mixes models.
        """
        if pin is not None:
            chain = [p for p in configed_providers if p.name == pin]
            if not chain:
                raise ValueError(f"pinned provider {pin!r} is not configured")
        else:
            chain = configed_providers
        if not chain:
            raise ValueError("no providers configured")

        failures: list[ProviderFailure] = []
        for provider in chain:
            start = time.monotonic()
            try:
                parsed, content, model = self._attempt_llm_call(
                    self.get_client(provider), messages, provider, schema
                )
            except ProviderFailure as failure:
                # Every provider-side failure moves on, 400s included: both 400s seen on
                # 14 Nov (temperature, schema) were Azure-only and Go took the same request.
                # A bug in our own code raises something else and isn't caught here.
                logger.warning("provider failed: %s %s", failure, failure.detail)
                failures.append(failure)
                continue
            return GatewayResult(
                parsed=parsed,
                content=content,
                provider=provider.name,
                model=model,
                temperature=provider.temperature,
                seconds=round(time.monotonic() - start, 1),
                failed_before=[str(f) for f in failures],
            )
        raise AllProvidersFailed(failures)

    def _attempt_llm_call(
        self,
        client: OpenAI,
        messages: list[dict],
        provider: ProviderConfig,
        schema: type[BaseModel],
    ) -> tuple[BaseModel, str, str]:
        try:
            completion = client.chat.completions.create(
                model=provider.model_name,
                messages=messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "llm_response",
                        "strict": True,
                        "schema": schema.model_json_schema(),
                    },
                },
                timeout=provider.timeout,
                # `is not None`, not truthiness: 0.0 is a valid temperature and it's falsy
                temperature=provider.temperature
                if provider.temperature is not None
                else omit,  # azure rejects temperature setting
                extra_body=provider.extra_body,
            )
        except openai.APIError as e:
            raise ProviderFailure(provider.name, _reason(e), str(e)[:300]) from e

        # a 200 can still be unusable, and the SDK doesn't raise for any of these
        if not completion.choices:
            raise ProviderFailure(provider.name, "no choices")
        choice = completion.choices[0]
        if choice.finish_reason == "length":
            raise ProviderFailure(provider.name, "cut off at token limit")
        if choice.finish_reason == "content_filter":
            raise ProviderFailure(provider.name, "content filter")
        if getattr(choice.message, "refusal", None):
            raise ProviderFailure(provider.name, "refused", choice.message.refusal[:300])
        content = choice.message.content
        if not content or not content.strip():
            raise ProviderFailure(provider.name, "empty answer")
        try:
            parsed = schema.model_validate_json(content)
        except ValidationError as e:
            raise ProviderFailure(provider.name, "answer fails schema", str(e)[:300]) from e

        return parsed, content, completion.model or provider.model_name


if __name__ == "__main__":
    print("configured providers:")
    if len(configed_providers) == 0:
        print("No providers configured")
    else:
        for provider in configed_providers:
            print(provider.name)
