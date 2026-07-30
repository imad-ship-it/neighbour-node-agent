"""Test doubles shared across app test suites.

Deliberately NOT in a tests.py: this is imported by apps.listings.tests and
apps.matching.tests, and importing across test modules breaks as soon as the
runner collects them in a different order.
"""

from contextlib import contextmanager
from unittest.mock import patch


class ScriptedProviderExhausted(AssertionError):
    """The code under test made more calls than the script had responses.

    An AssertionError, not a runtime error: it means the test's expectations were
    wrong (or the retry cap regressed), and it should fail loudly rather than
    look like a provider outage.
    """


class ScriptedProvider:
    """Stand-in LLM provider that returns queued responses in order.

    Records the call count and every prompt it received, so a test can assert not
    only the result but how many paid calls it took, and what the retry actually
    fed back to the model.
    """

    def __init__(self, *responses, raises=None):
        self._queue = list(responses)
        self._scripted = len(responses)
        self.raises = raises
        self.calls = 0
        self.prompts = []
        self.images = []

    def generate(self, prompt, image_base64=None, media_type="image/jpeg"):
        self.calls += 1
        self.prompts.append(prompt)
        self.images.append(image_base64)
        if self.raises is not None:
            raise self.raises
        if not self._queue:
            raise ScriptedProviderExhausted(
                f"provider call #{self.calls} had no scripted response "
                f"({self._scripted} were provided)"
            )
        return self._queue.pop(0)


@contextmanager
def scripted_provider(module_path, *responses, raises=None):
    """Patch get_provider inside one service module and yield the provider.

    Patches the name where it is USED, not where it is defined. Both services do
    `from apps.core.services.llm import get_provider`, which binds the function
    into their own module namespace — patching apps.core.services.llm would have
    no effect on them.

    Usage:
        with scripted_provider("apps.listings.services", RAW_JSON) as provider:
            result = extract_listing_from_image(png_bytes())
        self.assertEqual(provider.calls, 1)
    """
    provider = ScriptedProvider(*responses, raises=raises)
    with patch(f"{module_path}.get_provider", return_value=provider):
        yield provider
