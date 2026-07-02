import asyncio
import os
import unittest
from unittest.mock import patch

from ai_docs.config import ConfigError
from ai_docs.llm import LLMClient, from_env


class FakeAsyncClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.closed = False

    async def aclose(self):
        self.closed = True


class FakeOpenAIClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.closed = False

    async def aclose(self):
        self.closed = True


class LLMClientTlsTests(unittest.TestCase):
    def _patched_clients(self, instances):
        def make_http_client(**kwargs):
            client = FakeAsyncClient(**kwargs)
            instances.append(client)
            return client

        return (
            patch("ai_docs.llm.httpx.AsyncClient", side_effect=make_http_client),
            patch("ai_docs.llm.AsyncOpenAI"),
        )

    def test_verify_is_true_by_default(self):
        instances = []
        http_patch, openai_patch = self._patched_clients(instances)
        with http_patch, openai_patch:
            client = LLMClient(api_key="key", base_url="", model="model")

        self.assertTrue(client.verify)
        self.assertTrue(instances[0].kwargs["verify"])
        asyncio.run(client.aclose())
        self.assertTrue(instances[0].closed)

    def test_aclose_closes_openai_client_and_http_client(self):
        http_instances = []
        openai_instances = []

        def make_http_client(**kwargs):
            client = FakeAsyncClient(**kwargs)
            http_instances.append(client)
            return client

        def make_openai_client(**kwargs):
            client = FakeOpenAIClient(**kwargs)
            openai_instances.append(client)
            return client

        with patch("ai_docs.llm.httpx.AsyncClient", side_effect=make_http_client), \
             patch("ai_docs.llm.AsyncOpenAI", side_effect=make_openai_client):
            client = LLMClient(api_key="key", base_url="", model="model")
            asyncio.run(client.aclose())

        self.assertTrue(openai_instances[0].closed)
        self.assertTrue(http_instances[0].closed)

    def test_invalid_insecure_ssl_env_fails_explicitly(self):
        env = {
            "OPENAI_API_KEY": "key",
            "AI_DOCS_INSECURE_SSL": "maybe",
        }

        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ConfigError):
                from_env()

    def test_invalid_numeric_env_fails_explicitly(self):
        cases = [
            ("OPENAI_TEMPERATURE", "hot"),
            ("OPENAI_MAX_TOKENS", "many"),
            ("OPENAI_CONTEXT_TOKENS", "wide"),
            ("AI_DOCS_THREADS", "parallel"),
        ]
        for name, value in cases:
            with self.subTest(name=name):
                env = {
                    "OPENAI_API_KEY": "key",
                    name: value,
                }
                with patch.dict(os.environ, env, clear=True):
                    with self.assertRaises(ConfigError):
                        from_env()

    def test_insecure_ssl_env_is_explicit_opt_in(self):
        instances = []
        http_patch, openai_patch = self._patched_clients(instances)
        env = {
            "OPENAI_API_KEY": "key",
            "AI_DOCS_INSECURE_SSL": "true",
        }

        with patch.dict(os.environ, env, clear=True), \
             patch("ai_docs.llm.get_logger") as get_logger, \
             http_patch, openai_patch:
            client = from_env()

        self.assertFalse(client.verify)
        self.assertFalse(instances[0].kwargs["verify"])
        get_logger.return_value.warning.assert_called_once()
        self.assertIn("AI_DOCS_INSECURE_SSL", get_logger.return_value.warning.call_args.args[0])
        asyncio.run(client.aclose())

    def test_async_context_manager_closes_http_client(self):
        instances = []
        http_patch, openai_patch = self._patched_clients(instances)

        async def scenario():
            async with LLMClient(api_key="key", base_url="", model="model") as client:
                self.assertFalse(instances[0].closed)
                self.assertTrue(client.verify)

        with http_patch, openai_patch:
            asyncio.run(scenario())

        self.assertTrue(instances[0].closed)


class LLMClientResponseValidationTests(unittest.TestCase):
    def _client_with_response(self, response):
        client = LLMClient(api_key="key", base_url="", model="model")

        class FakeCompletions:
            async def create(self, **kwargs):
                return response

        class FakeChat:
            completions = FakeCompletions()

        class FakeClient:
            chat = FakeChat()

        client._client = FakeClient()
        return client

    def _response(self, content, finish_reason="stop"):
        class _Msg:
            pass

        class _Choice:
            pass

        class _Resp:
            pass

        message = _Msg()
        message.content = content
        choice = _Choice()
        choice.message = message
        choice.finish_reason = finish_reason
        resp = _Resp()
        resp.choices = [choice]
        return resp

    def test_none_content_is_not_cached(self):
        client = self._client_with_response(self._response(None))
        cache = {}

        async def scenario():
            with self.assertRaises(RuntimeError) as raised:
                await client.chat([{"role": "user", "content": "hello"}], cache=cache)
            self.assertIn("empty content", str(raised.exception))

        try:
            asyncio.run(scenario())
            self.assertEqual(cache, {})
        finally:
            asyncio.run(client.aclose())

    def test_length_finish_reason_is_not_cached(self):
        client = self._client_with_response(self._response("partial", finish_reason="length"))
        cache = {}

        async def scenario():
            with self.assertRaises(RuntimeError) as raised:
                await client.chat([{"role": "user", "content": "hello"}], cache=cache)
            self.assertIn("finish_reason", str(raised.exception))

        try:
            asyncio.run(scenario())
            self.assertEqual(cache, {})
        finally:
            asyncio.run(client.aclose())

    def test_invalid_cache_hit_fails_explicitly(self):
        client = LLMClient(api_key="key", base_url="", model="model")
        messages = [{"role": "user", "content": "hello"}]
        payload = {
            "model": client.model,
            "messages": messages,
            "temperature": client.temperature,
            "max_tokens": client.max_tokens,
        }
        cache = {client._cache_key(payload): None}

        async def scenario():
            with self.assertRaises(RuntimeError) as raised:
                await client.chat(messages, cache=cache)
            self.assertIn("Invalid cached LLM response", str(raised.exception))

        try:
            asyncio.run(scenario())
        finally:
            asyncio.run(client.aclose())


if __name__ == "__main__":
    unittest.main()
