"""Sends a prompt to the LLM chosen in .env and returns its reply as structured JSON (US-7, US-12).

The provider is picked with LLM_PROVIDER, so switching between OpenRouter, Claude and Gemini
only means editing .env (see .env.example). Nothing here runs unless LLM_PROVIDER is set.

Each call makes one request for one reply. It never resends the same request itself: a reply that is
cut off at the output limit is reported (ReplyCutOffError), because sending it again would be cut off
the same way, and an unreadable reply is reported (UnreadableReplyError) so the caller can decide
whether to ask again (llm_review.review_contract asks once more). The SDKs still retry a request that
failed to reach the provider, was rate-limited, or hit a server error, with their own backoff.
"""
import json
import os
import re

# How long to wait for the provider before giving up, unless LLM_TIMEOUT_SECONDS says otherwise
DEFAULT_TIMEOUT_SECONDS = 300
# Claude's output limit, unless LLM_MAX_TOKENS says otherwise. Other providers use their own default
# unless LLM_MAX_TOKENS is set.
DEFAULT_ANTHROPIC_MAX_TOKENS = 16000
# Retries the SDKs make for connection errors, rate limits (429) and server errors (5xx), with backoff
SDK_MAX_RETRIES = 1  # at most 2 requests per call: free tiers count retries against their limits
EFFORTS = ("low", "medium", "high")

# Providers that speak the OpenAI chat-completions format. Switching between them only changes
# the base URL, the environment variable holding the key, and the default model.
_OPENAI_COMPATIBLE_PRESETS = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "default_model": "nvidia/nemotron-3.5-super-vl:free",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GEMINI_API_KEY",
        "default_model": "gemini-2.5-flash",
    },
}

_ANTHROPIC_DEFAULT_MODEL = "claude-opus-5-5"

PROVIDERS = sorted([*_OPENAI_COMPATIBLE_PRESETS, "anthropic"])

# The .env settings that hold API keys, and the shapes of the providers' keys (Anthropic sk-ant-...,
# OpenRouter sk-or-v1-..., Google AIza...), so keys can be kept out of logs and out of the repository
KEY_ENVS = ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY")
KEY_PATTERN = re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}|sk-or-v1-[A-Za-z0-9]{8,}|AIza[0-9A-Za-z_-]{20,}")
REDACTED = "[redacted key]"


# Returns text with every configured API key, and anything shaped like a provider key, replaced
def redact_keys(text):
    for key_env in KEY_ENVS:
        value = os.environ.get(key_env, "").strip()
        if len(value) >= 8:
            text = text.replace(value, REDACTED)
    return KEY_PATTERN.sub(REDACTED, text)


# A problem with the .env settings (missing key, unknown provider, invalid limit), as opposed to a failed call
class LLMConfigError(RuntimeError):
    pass


# The provider did not answer within the timeout
class LLMTimeoutError(RuntimeError):
    pass


# The reply stopped at the output limit before it was complete
class ReplyCutOffError(RuntimeError):
    pass


# The reply could not be read as the structured output that was asked for
class UnreadableReplyError(ValueError):
    pass


# Returns the provider named in .env, or None when no LLM is configured
def provider_name():
    name = os.environ.get("LLM_PROVIDER", "").strip().lower()
    return name if name and name != "none" else None


# Returns the model the configured provider will use (LLM_MODEL, or the provider's default)
def model_name():
    provider = provider_name()
    if provider == "anthropic":
        return os.environ.get("LLM_MODEL") or _ANTHROPIC_DEFAULT_MODEL
    if provider in _OPENAI_COMPATIBLE_PRESETS:
        return os.environ.get("LLM_MODEL") or _OPENAI_COMPATIBLE_PRESETS[provider]["default_model"]
    return None


# Reads a positive number from .env, or returns `default` when the setting is empty
def _positive_setting(name, default, kind):
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    try:
        number = kind(value)
    except ValueError:
        number = 0
    if not number > 0:  # also turns down "nan"
        whole = " whole" if kind is int else ""
        raise LLMConfigError(f"{name} must be a{whole} number greater than 0, not '{value}'")
    return number


# Seconds to wait for the provider (LLM_TIMEOUT_SECONDS). For Claude the reply is streamed, so this is the
# longest the provider may go without sending anything.
def timeout_seconds():
    return _positive_setting("LLM_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS, float)


# The reply's output limit from LLM_MAX_TOKENS, or None to use the default
def max_tokens_setting():
    return _positive_setting("LLM_MAX_TOKENS", None, int)


# How much the model may think before answering (LLM_EFFORT: low, medium or high), or None for its default
def effort_setting():
    value = os.environ.get("LLM_EFFORT", "").strip().lower()
    if not value:
        return None
    if value not in EFFORTS:
        raise LLMConfigError(f"LLM_EFFORT must be one of {', '.join(EFFORTS)}, not '{value}'")
    return value


# Returns why the AI review cannot run with the current settings (no provider, unknown provider,
# missing key, or an invalid limit), or None when it can. Checks the settings only; it does not call
# the provider.
def configuration_problem():
    provider = provider_name()
    if provider is None:
        return "LLM_PROVIDER is not set in .env"
    if provider == "anthropic":
        key_env = "ANTHROPIC_API_KEY"
    elif provider in _OPENAI_COMPATIBLE_PRESETS:
        key_env = _OPENAI_COMPATIBLE_PRESETS[provider]["key_env"]
    else:
        return f"Unknown LLM_PROVIDER '{provider}'. Expected one of: {', '.join(PROVIDERS)}"
    if not os.environ.get(key_env):
        return f"{key_env} is not set in .env (needed for LLM_PROVIDER={provider})"
    try:
        timeout_seconds(), max_tokens_setting(), effort_setting()
    except LLMConfigError as error:
        return str(error)
    return None


# Pulls a JSON object out of a plain-text reply, tolerating ```json fences or a sentence around it
def _parse_json_text(text):
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


def _timed_out(provider):
    return LLMTimeoutError(f"{provider} did not answer within {timeout_seconds():g} seconds (LLM_TIMEOUT_SECONDS)")


def _cut_off(provider, limit):
    return ReplyCutOffError(f"The reply from {provider} was cut off at its output limit ({limit}); "
                            "raise LLM_MAX_TOKENS or lower LLM_EFFORT")


# One chat-completions request; a timeout or a reply stopped at the output limit is reported, not retried
def _chat_completion(provider, client, **request):
    import openai
    try:
        response = client.chat.completions.create(**request)
    except openai.APITimeoutError as error:
        raise _timed_out(provider) from error
    if response.choices[0].finish_reason == "length":
        raise _cut_off(provider, request.get("max_tokens") or "the provider's default")
    return response


def _openai_compatible(provider, prompt, schema, schema_name):
    import openai

    preset = _OPENAI_COMPATIBLE_PRESETS[provider]
    client = openai.OpenAI(base_url=preset["base_url"], api_key=os.environ.get(preset["key_env"]),
                           timeout=timeout_seconds(), max_retries=SDK_MAX_RETRIES)
    options = {"model": os.environ.get("LLM_MODEL") or preset["default_model"], "temperature": 0}
    if max_tokens_setting():
        options["max_tokens"] = max_tokens_setting()
    if effort_setting():
        options["reasoning_effort"] = effort_setting()
    tool = {
        "type": "function",
        "function": {"name": schema_name, "description": schema.get("description", ""), "parameters": schema},
    }

    # Preferred path: force the model to call our tool so the arguments are structured JSON
    try:
        response = _chat_completion(provider, client, tools=[tool],
                                    tool_choice={"type": "function", "function": {"name": schema_name}},
                                    messages=[{"role": "user", "content": prompt}], **options)
    except openai.BadRequestError:
        # The model does not support forced tool calls (rejected at once, nothing generated): ask for raw JSON
        json_prompt = (
            f"{prompt}\n\nRespond with ONLY a JSON object (no prose, no code fences) "
            f"that matches this JSON schema:\n{json.dumps(schema)}"
        )
        response = _chat_completion(provider, client, messages=[{"role": "user", "content": json_prompt}], **options)
        return _parse_json_text(response.choices[0].message.content)

    message = response.choices[0].message
    if message.tool_calls:
        return json.loads(message.tool_calls[0].function.arguments)
    # Some models answer in text even when asked for a tool call; read the JSON from the text instead
    return _parse_json_text(message.content)


def _anthropic(prompt, schema, schema_name):
    import anthropic

    client = anthropic.Anthropic(timeout=timeout_seconds(), max_retries=SDK_MAX_RETRIES)
    limit = max_tokens_setting() or DEFAULT_ANTHROPIC_MAX_TOKENS
    output_config = {"format": {"type": "json_schema", "schema": schema}}
    if effort_setting():
        output_config["effort"] = effort_setting()
    # Structured outputs guarantee the reply matches the schema. If Claude declines a request, the
    # server-side fallback re-runs it on another Claude model in the same call. The reply is streamed,
    # so a large LLM_MAX_TOKENS works too.
    try:
        with client.beta.messages.stream(
            model=os.environ.get("LLM_MODEL") or _ANTHROPIC_DEFAULT_MODEL,
            max_tokens=limit,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config=output_config,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            response = stream.get_final_message()
    except anthropic.APITimeoutError as error:
        raise _timed_out("anthropic") from error

    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to review this contract")
    if response.stop_reason == "max_tokens":
        raise _cut_off("anthropic", limit)

    text = next(block.text for block in response.content if block.type == "text")
    return json.loads(text)


# Sends a prompt to the provider LLM_PROVIDER names and returns the reply as a dict matching `schema`.
# Makes one request; configuration problems are raised before anything is sent (LLMConfigError), and a
# reply that cannot be read is raised as UnreadableReplyError for the caller to retry or report.
def generate_structured(prompt, schema, schema_name):
    problem = configuration_problem()
    if problem:
        raise LLMConfigError(problem)

    provider = provider_name()
    try:
        if provider == "anthropic":
            return _anthropic(prompt, schema, schema_name)
        return _openai_compatible(provider, prompt, schema, schema_name)
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, StopIteration) as error:
        raise UnreadableReplyError(f"The reply from {provider} was not valid structured output") from error
