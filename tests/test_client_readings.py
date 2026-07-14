import datetime
from unittest.mock import MagicMock

import pytest

from oejp_exporter.client import OEJPClient


@pytest.fixture
def authed_client():
    client = OEJPClient(user_email="me@example.com", user_password="secret")
    # pre-seed a valid token so get_half_hour_reading does not authenticate
    client._token = "tok"
    client._token_expiry = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1)
    session = MagicMock()
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"data": {}}
    session.post.return_value = resp
    client._session = session
    return client


def test_get_half_hour_reading_sends_account_and_window(authed_client):
    authed_client.get_half_hour_reading("A-99")

    call = authed_client._session.post.call_args
    body = call.kwargs["json"]
    assert body["variables"]["accountNumber"] == "A-99"
    assert "fromDatetime" in body["variables"]
    assert "toDatetime" in body["variables"]
    assert call.kwargs["headers"] == {"authorization": "JWT tok"}


def test_get_half_hour_reading_honours_explicit_window(authed_client):
    frm = datetime.datetime(2026, 7, 1, tzinfo=datetime.UTC)
    to = datetime.datetime(2026, 7, 2, tzinfo=datetime.UTC)
    authed_client.get_half_hour_reading("A-99", from_datetime=frm, to_datetime=to)

    variables = authed_client._session.post.call_args.kwargs["json"]["variables"]
    assert variables["fromDatetime"] == frm.isoformat()
    assert variables["toDatetime"] == to.isoformat()
