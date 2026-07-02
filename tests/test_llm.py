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
             patch("builtins.print") as print_mock, \
             http_patch, openai_patch:
            client = from_env()

        self.assertFalse(client.verify)
        self.assertFalse(instances[0].kwargs["verify"])
        self.assertTrue(
            any("AI_DOCS_INSECURE_SSL" in str(call.args[0]) for call in print_mock.call_args_list)
        )
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


if __name__ == "__main__":
    unittest.main()
