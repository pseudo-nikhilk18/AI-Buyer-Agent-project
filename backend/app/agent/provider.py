from dataclasses import dataclass

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.config import Settings, get_settings


class ProviderConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedProvider:
    name: str
    model: str


def resolve_provider(settings: Settings | None = None) -> ResolvedProvider | None:
    configured = settings or get_settings()
    if configured.ai_mode == "replay":
        return None

    keys = {
        "gemini": configured.gemini_api_key,
        "openai": configured.openai_api_key,
        "anthropic": configured.anthropic_api_key,
    }
    available = [name for name, key in keys.items() if key is not None]
    provider = configured.llm_provider
    if provider is None:
        if len(available) != 1:
            raise ProviderConfigurationError(
                "Live mode requires LLM_PROVIDER when zero or multiple provider keys are configured."
            )
        provider = available[0]
    if keys[provider] is None:
        raise ProviderConfigurationError(f"Live mode is missing the API key for {provider}.")
    if not configured.llm_model:
        raise ProviderConfigurationError("Live mode requires LLM_MODEL.")
    return ResolvedProvider(name=provider, model=configured.llm_model)


def resolve_run_provider(
    mode: str,
    provider_name: str | None,
    model: str | None,
    settings: Settings | None = None,
) -> ResolvedProvider | None:
    if mode == "replay":
        return None
    if provider_name not in {"gemini", "openai", "anthropic"} or not model:
        raise ProviderConfigurationError("The saved live run has invalid provider metadata.")

    configured = settings or get_settings()
    keys = {
        "gemini": configured.gemini_api_key,
        "openai": configured.openai_api_key,
        "anthropic": configured.anthropic_api_key,
    }
    if keys[provider_name] is None:
        raise ProviderConfigurationError(
            f"Resuming this run requires the API key for {provider_name}."
        )
    return ResolvedProvider(name=provider_name, model=model)


def create_chat_model(provider: ResolvedProvider, settings: Settings | None = None) -> BaseChatModel:
    configured = settings or get_settings()
    if provider.name == "gemini":
        return ChatGoogleGenerativeAI(
            model=provider.model,
            api_key=configured.gemini_api_key,
            temperature=0,
            retries=1,
            request_timeout=30,
        )
    if provider.name == "openai":
        return ChatOpenAI(
            model=provider.model,
            api_key=configured.openai_api_key,
            temperature=0,
            max_retries=1,
            timeout=30,
        )
    return ChatAnthropic(
        model_name=provider.model,
        api_key=configured.anthropic_api_key,
        temperature=0,
        max_retries=1,
        timeout=30,
    )
