"""Limits on AI calls (US-12 robustness): a request timeout, no resending of a reply cut off at the output
limit, at most two replies per contract, and optional output limit and effort settings. The OpenAI and
Anthropic SDK clients are replaced with fakes, so nothing is sent anywhere."""
from contextlib import nullcontext
from types import SimpleNamespace as NS

import anthropic
import httpx
import openai
import pytest

import llm_providers
import llm_review
import main
from flag_problem_language import load_tnc_matrix
from llm_providers import LLMConfigError, LLMTimeoutError, ReplyCutOffError

TNC = load_tnc_matrix(main.TNC_MATRIX_PATH)
CONTRACT = "This Agreement begins on January 1. The Sponsor shall own all intellectual property."
SCHEMA = {"type": "object", "properties": {"issues": {"type": "array"}}}
NO_ISSUES = '{"issues": []}'
LIMIT_SETTINGS = ("LLM_MODEL", "LLM_MAX_TOKENS", "LLM_EFFORT", "LLM_TIMEOUT_SECONDS")
REQUEST = httpx.Request("POST", "https://provider.invalid/v1")


class FakeClient:
    """Stands in for openai.OpenAI or anthropic.Anthropic: records the client's options and each request,
    and answers each request with the next of `replies` (an exception in the list is raised)."""

    def __init__(self, replies):
        self.replies, self.requests, self.options = list(replies), [], None
        self.chat = NS(completions=NS(create=self._answer))  # OpenAI: client.chat.completions.create
        self.beta = NS(messages=NS(stream=self._stream))  # Anthropic: client.beta.messages.stream

    def __call__(self, **options):  # the code calls the class: openai.OpenAI(**options)
        self.options = options
        return self

    def _answer(self, **request):
        self.requests.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def _stream(self, **request):
        reply = self._answer(**request)
        return nullcontext(NS(get_final_message=lambda: reply))


def completion(arguments=None, content=None, finish_reason="stop"):
    tool_calls = [NS(function=NS(arguments=arguments))] if arguments is not None else None
    return NS(choices=[NS(finish_reason=finish_reason, message=NS(tool_calls=tool_calls, content=content))])


def claude_message(text=NO_ISSUES, stop_reason="end_turn"):
    return NS(stop_reason=stop_reason, content=[NS(type="text", text=text)])


@pytest.fixture
def provider(monkeypatch):
    """Returns a function that sets up `name` with a fake key and a FakeClient answering with `replies`."""
    for setting in LIMIT_SETTINGS:
        monkeypatch.delenv(setting, raising=False)

    def install(name, replies):
        fake = FakeClient(replies)
        monkeypatch.setenv("LLM_PROVIDER", name)
        if name == "anthropic":
            monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
            monkeypatch.setattr(anthropic, "Anthropic", fake)
        else:
            monkeypatch.setenv("GEMINI_API_KEY", "test-key")
            monkeypatch.setattr(openai, "OpenAI", fake)
        return fake
    return install


def test_client_gets_the_timeout_and_limits_are_only_sent_when_set(provider, monkeypatch):
    fake = provider("gemini", [completion(arguments=NO_ISSUES), completion(arguments=NO_ISSUES)])
    assert llm_providers.generate_structured("prompt", SCHEMA, "report") == {"issues": []}
    assert (fake.options["timeout"], fake.options["max_retries"]) == (300, llm_providers.SDK_MAX_RETRIES)
    assert "max_tokens" not in fake.requests[0] and "reasoning_effort" not in fake.requests[0]

    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("LLM_MAX_TOKENS", "8000")
    monkeypatch.setenv("LLM_EFFORT", "Low")
    llm_providers.generate_structured("prompt", SCHEMA, "report")
    assert fake.options["timeout"] == 45
    assert (fake.requests[1]["max_tokens"], fake.requests[1]["reasoning_effort"]) == (8000, "low")


def test_reply_cut_off_at_the_limit_is_reported_and_not_resent(provider):
    fake = provider("gemini", [completion(arguments='{"issues": [{"quo', finish_reason="length")])
    with pytest.raises(ReplyCutOffError, match="cut off"):
        llm_review.review_contract(CONTRACT, TNC)
    assert len(fake.requests) == 1


def test_timeout_is_reported_and_not_resent(provider):
    fake = provider("gemini", [openai.APITimeoutError(request=REQUEST)])
    with pytest.raises(main.AIReviewError, match=r"AI service \(gemini\) did not answer in time") as raised:
        main.ai_flags(CONTRACT)
    assert isinstance(raised.value.__cause__, LLMTimeoutError) and "300 seconds" in str(raised.value.__cause__)
    assert len(fake.requests) == 1


def test_unreadable_reply_is_asked_for_once_more_then_reported(provider):
    fake = provider("gemini", [completion(content="Sorry, no JSON."), completion(arguments=NO_ISSUES)])
    assert llm_review.review_contract(CONTRACT, TNC) == []
    assert len(fake.requests) == 2

    fake = provider("gemini", [completion(content="Sorry, no JSON.")] * 3)
    with pytest.raises(ValueError, match="list of issues after 2 attempts"):
        llm_review.review_contract(CONTRACT, TNC)
    assert len(fake.requests) == llm_review.MAX_REPLY_ATTEMPTS == 2


def test_text_answer_instead_of_a_tool_call_is_read_without_another_request(provider):
    fake = provider("gemini", [completion(content=f"Here are the issues: {NO_ISSUES}")])
    assert llm_providers.generate_structured("prompt", SCHEMA, "report") == {"issues": []}
    assert len(fake.requests) == 1


def test_model_without_forced_tool_calls_is_asked_for_raw_json(provider):
    rejected = openai.BadRequestError("tool_choice is not supported", response=httpx.Response(400, request=REQUEST),
                                      body=None)
    fake = provider("gemini", [rejected, completion(content=f"```json\n{NO_ISSUES}\n```")])
    assert llm_providers.generate_structured("prompt", SCHEMA, "report") == {"issues": []}
    assert "tools" not in fake.requests[1]
    assert "Respond with ONLY a JSON object" in fake.requests[1]["messages"][0]["content"]


def test_cancelled_scan_does_not_ask_for_a_second_reply(provider):
    fake = provider("gemini", [completion(content="Sorry, no JSON."), completion(arguments=NO_ISSUES)])

    def cancelled():
        raise main.ScanCancelled
    with pytest.raises(main.ScanCancelled):  # not turned into a failed AI review
        main.ai_flags(CONTRACT, before_retry=cancelled)
    assert len(fake.requests) == 1


def test_claude_reply_is_streamed_with_the_output_limit_and_effort(provider, monkeypatch):
    monkeypatch.setenv("LLM_EFFORT", "high")
    fake = provider("anthropic", [claude_message()])
    assert llm_providers.generate_structured("prompt", SCHEMA, "report") == {"issues": []}
    (request,) = fake.requests
    assert request["max_tokens"] == llm_providers.DEFAULT_ANTHROPIC_MAX_TOKENS
    assert request["output_config"] == {"format": {"type": "json_schema", "schema": SCHEMA}, "effort": "high"}
    assert (fake.options["timeout"], fake.options["max_retries"]) == (300, llm_providers.SDK_MAX_RETRIES)


def test_claude_reply_cut_off_at_the_limit_is_reported_and_not_resent(provider, monkeypatch):
    monkeypatch.setenv("LLM_MAX_TOKENS", "32000")
    fake = provider("anthropic", [claude_message('{"issues": [', stop_reason="max_tokens")])
    with pytest.raises(main.AIReviewError, match="raise LLM_MAX_TOKENS") as raised:
        main.ai_flags(CONTRACT)
    assert "32000" in str(raised.value.__cause__)
    assert len(fake.requests) == 1


def test_claude_timeout_is_reported(provider):
    provider("anthropic", [anthropic.APITimeoutError(request=REQUEST)])
    with pytest.raises(LLMTimeoutError, match="anthropic did not answer within 300 seconds"):
        llm_providers.generate_structured("prompt", SCHEMA, "report")


@pytest.mark.parametrize("setting, value", [
    ("LLM_TIMEOUT_SECONDS", "0"), ("LLM_TIMEOUT_SECONDS", "soon"), ("LLM_TIMEOUT_SECONDS", "nan"),
    ("LLM_MAX_TOKENS", "1.5"), ("LLM_MAX_TOKENS", "-1"), ("LLM_EFFORT", "extreme"),
])
def test_invalid_limits_are_reported_before_anything_is_sent(provider, monkeypatch, setting, value):
    fake = provider("gemini", [])
    monkeypatch.setenv(setting, value)
    assert setting in llm_providers.configuration_problem()
    with pytest.raises(LLMConfigError, match=setting):
        llm_providers.generate_structured("prompt", SCHEMA, "report")
    assert fake.options is None  # no client was even created
