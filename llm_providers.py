"""Sends a prompt to the LLM chosen in .env and returns its reply as structured JSON (US-7, US-12).

The provider is picked with LLM_PROVIDER, so switching between OpenRouter, Claude and Gemini
only means editing .env (see .env.example). Nothing here runs unless LLM_PROVIDER is set.
"""
import json
import os
import re

MAX_JSON_RETRIES = 3

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


# A problem with the .env settings (missing key, unknown provider), as opposed to a failed call
class LLMConfigError(RuntimeError):
    pass


# Returns the provider named in .env, or None when no LLM is configured
def provider_name():
    name = os.environ.get("LLM_PROVIDER", "").strip().lower()
    return name if name and name != "none" else None


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


def _openai_compatible(provider, prompt, schema, schema_name):
    from openai import OpenAI, BadRequestError

    preset = _OPENAI_COMPATIBLE_PRESETS[provider]
    api_key = os.environ.get(preset["key_env"])
    if not api_key:
        raise LLMConfigError(f"{preset['key_env']} is not set in .env (needed for LLM_PROVIDER={provider})")

    model = os.environ.get("LLM_MODEL") or preset["default_model"]
    client = OpenAI(base_url=preset["base_url"], api_key=api_key)
    tool = {
        "type": "function",
        "function": {"name": schema_name, "description": schema.get("description", ""), "parameters": schema},
    }

    # Preferred path: force the model to call our tool so the arguments are structured JSON.
    # Some models don't support forced tool calls, so fall back to asking for raw JSON.
    try:
        response = client.chat.completions.create(
            model=model,
            tools=[tool],
            tool_choice={"type": "function", "function": {"name": schema_name}},
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        tool_calls = response.choices[0].message.tool_calls
        if tool_calls:
            return json.loads(tool_calls[0].function.arguments)
    except BadRequestError:
        pass

    json_prompt = (
        f"{prompt}\n\nRespond with ONLY a JSON object (no prose, no code fences) "
        f"that matches this JSON schema:\n{json.dumps(schema)}"
    )
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": json_prompt}],
        temperature=0,
    )
    return _parse_json_text(response.choices[0].message.content)


def _anthropic(prompt, schema, schema_name):
    import anthropic

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise LLMConfigError("ANTHROPIC_API_KEY is not set in .env (needed for LLM_PROVIDER=anthropic)")

    client = anthropic.Anthropic()
    # Structured outputs guarantee the reply matches the schema. If Claude declines a request,
    # the server-side fallback re-runs it on another Claude model in the same call.
    response = client.beta.messages.create(
        model=os.environ.get("LLM_MODEL") or _ANTHROPIC_DEFAULT_MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": prompt}],
    )

    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to review this contract")
    if response.stop_reason == "max_tokens":
        raise json.JSONDecodeError("Response hit max_tokens before the JSON was complete", "", 0)

    text = next(block.text for block in response.content if block.type == "text")
    return json.loads(text)


# Sends a prompt to the provider LLM_PROVIDER names and returns the reply as a dict matching
# `schema`. Retries when the model returns malformed JSON; configuration problems (missing key,
# unknown provider) are raised immediately with a readable message.
def generate_structured(prompt, schema, schema_name):
    provider = provider_name()
    if provider is None:
        raise LLMConfigError("LLM_PROVIDER is not set in .env")

    if provider == "anthropic":
        call = lambda: _anthropic(prompt, schema, schema_name)
    elif provider in _OPENAI_COMPATIBLE_PRESETS:
        call = lambda: _openai_compatible(provider, prompt, schema, schema_name)
    else:
        raise LLMConfigError(f"Unknown LLM_PROVIDER '{provider}'. Expected one of: {', '.join(PROVIDERS)}")

    last_error = None
    for _ in range(MAX_JSON_RETRIES):
        try:
            return call()
        except (json.JSONDecodeError, KeyError, IndexError, TypeError, StopIteration) as error:
            last_error = error

    raise RuntimeError(
        f"LLM provider '{provider}' did not return valid structured output after {MAX_JSON_RETRIES} attempts"
    ) from last_error
