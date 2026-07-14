import signal
import threading

import pytest

from main import build_collector, install_shutdown_handlers
from oejp_exporter.client import DEFAULT_API_ENDPOINT


def test_build_collector_requires_credentials():
    with pytest.raises(ValueError):
        build_collector(env={})
    with pytest.raises(ValueError):
        build_collector(env={"OEJP_EMAIL": "me@example.com"})  # password missing


def test_build_collector_uses_env_credentials_and_default_endpoint():
    collector = build_collector(env={
        "OEJP_EMAIL": "me@example.com",
        "OEJP_PASSWORD": "secret",
    })
    assert collector._user_email == "me@example.com"
    assert collector._user_password == "secret"
    assert collector._api_endpoint == DEFAULT_API_ENDPOINT


def test_build_collector_honours_endpoint_override():
    collector = build_collector(env={
        "OEJP_EMAIL": "me@example.com",
        "OEJP_PASSWORD": "secret",
        "OEJP_API_ENDPOINT": "https://custom.example/graphql/",
    })
    assert collector._api_endpoint == "https://custom.example/graphql/"


@pytest.fixture
def restore_signal_handlers():
    saved = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
    yield
    for s, handler in saved.items():
        signal.signal(s, handler)


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
def test_install_shutdown_handlers_sets_event_on_signal(sig, restore_signal_handlers):
    stop = threading.Event()
    install_shutdown_handlers(stop)

    assert not stop.is_set()
    handler = signal.getsignal(sig)
    handler(sig, None)  # simulate the signal being delivered
    assert stop.is_set()
