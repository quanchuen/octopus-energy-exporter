import datetime
from unittest.mock import MagicMock, patch

import pytest

from oejp_exporter.client import OEJPClient


def _now():
    return datetime.datetime.now(datetime.UTC)


def make_auth_response(token, refresh_token="refresh-abc",
                       token_exp=None, refresh_expires_in=3600):
    """Build a fake requests.Response for an obtainKrakenToken call."""
    if token_exp is None:
        token_exp = _now() + datetime.timedelta(seconds=3600)
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "data": {
            "obtainKrakenToken": {
                "token": token,
                "refreshToken": refresh_token,
                "refreshExpiresIn": refresh_expires_in,
                "payload": {"exp": int(token_exp.timestamp())},
            }
        }
    }
    return resp


def _sent_input(call):
    """Extract the obtainKrakenToken input dict from a mocked post call."""
    return call.kwargs["json"]["variables"]["input"]


@pytest.fixture
def client():
    return OEJPClient(user_email="me@example.com", user_password="secret")


def test_first_token_access_authenticates_with_credentials(client):
    with patch("oejp_exporter.client.requests.post") as post:
        post.return_value = make_auth_response(token="tok-1")
        assert client.token == "tok-1"

    assert post.call_count == 1
    assert _sent_input(post.call_args) == {
        "email": "me@example.com",
        "password": "secret",
    }


def test_valid_token_is_cached_across_accesses(client):
    with patch("oejp_exporter.client.requests.post") as post:
        post.return_value = make_auth_response(token="tok-1")
        assert client.token == "tok-1"
        assert client.token == "tok-1"

    assert post.call_count == 1  # not re-authenticated


def test_expired_token_refreshes_with_refresh_token(client):
    past = _now() - datetime.timedelta(seconds=10)
    future = _now() + datetime.timedelta(seconds=3600)
    with patch("oejp_exporter.client.requests.post") as post:
        post.side_effect = [
            make_auth_response(token="tok-1", refresh_token="refresh-1",
                               token_exp=past, refresh_expires_in=3600),
            make_auth_response(token="tok-2", refresh_token="refresh-2",
                               token_exp=future, refresh_expires_in=3600),
        ]
        assert client.token == "tok-1"  # initial auth (already expired)
        assert client.token == "tok-2"  # triggers refresh

    assert post.call_count == 2
    assert _sent_input(post.call_args_list[0]) == {
        "email": "me@example.com", "password": "secret",
    }
    assert _sent_input(post.call_args_list[1]) == {"refreshToken": "refresh-1"}


def test_refresh_rolls_the_refresh_token_forward(client):
    past = _now() - datetime.timedelta(seconds=10)
    future = _now() + datetime.timedelta(seconds=3600)
    with patch("oejp_exporter.client.requests.post") as post:
        post.side_effect = [
            make_auth_response(token="tok-1", refresh_token="refresh-1",
                               token_exp=past),
            make_auth_response(token="tok-2", refresh_token="refresh-2",
                               token_exp=future),
        ]
        client.token  # initial auth
        client.token  # refresh

    # the fresh refresh token from the refresh response is adopted (rotation)
    assert client._refresh_token == "refresh-2"


def test_expired_refresh_token_reauthenticates_with_credentials(client):
    past = _now() - datetime.timedelta(seconds=10)
    with patch("oejp_exporter.client.requests.post") as post:
        post.side_effect = [
            # initial token expired, refresh token also already expired
            make_auth_response(token="tok-1", refresh_token="refresh-1",
                               token_exp=past, refresh_expires_in=0),
            make_auth_response(token="tok-2", refresh_token="refresh-2"),
        ]
        assert client.token == "tok-1"
        assert client.token == "tok-2"

    assert _sent_input(post.call_args_list[1]) == {
        "email": "me@example.com", "password": "secret",
    }


def test_refresh_failure_falls_back_to_reauth(client):
    past = _now() - datetime.timedelta(seconds=10)
    with patch("oejp_exporter.client.requests.post") as post:
        post.side_effect = [
            make_auth_response(token="tok-1", refresh_token="refresh-1",
                               token_exp=past, refresh_expires_in=3600),
            RuntimeError("refresh endpoint down"),
            make_auth_response(token="tok-2"),
        ]
        assert client.token == "tok-1"
        assert client.token == "tok-2"

    assert post.call_count == 3
    assert _sent_input(post.call_args_list[1]) == {"refreshToken": "refresh-1"}
    assert _sent_input(post.call_args_list[2]) == {
        "email": "me@example.com", "password": "secret",
    }
