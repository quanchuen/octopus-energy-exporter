from unittest.mock import MagicMock

import pytest

from oejp_exporter.client import OEJPClient
from oejp_exporter.metrics import OEJPCollector


def make_reading(value, cost, end_at, rate_band="OFF_PEAK", step=1):
    return {
        "value": value,
        "costEstimate": cost,
        "startAt": end_at,
        "endAt": end_at,
        "consumptionRateBand": rate_band,
        "consumptionStep": step,
    }


def make_supply_details(
    amperage="30", kva="6", kw="6.0", valid_from="2025-04-01T00:00:00+00:00"
):
    return {"amperage": amperage, "kva": kva, "kw": kw, "validFrom": valid_from}


def reading_response(readings, supply_details=None):
    point = {"halfHourlyReadings": readings}
    if supply_details is not None:
        # the API returns supplyDetails as a list; collect() reads the first entry
        point["supplyDetails"] = [supply_details]
    return {
        "data": {
            "account": {
                "properties": [
                    {"electricitySupplyPoints": [point]}
                ]
            }
        }
    }


@pytest.fixture
def collector():
    return OEJPCollector(
        user_email="me@example.com",
        user_password="secret",
        api_endpoint="https://api.example/graphql/",
    )


def _samples_by_account(family):
    return {s.labels["account"]: s.value for s in family.samples}


def _labels_by_account(family):
    return {s.labels["account"]: dict(s.labels) for s in family.samples}


def test_client_property_builds_and_caches_client(collector):
    first = collector.client
    assert isinstance(first, OEJPClient)
    assert collector.client is first  # cached, not rebuilt


def test_collect_emits_latest_reading_per_account(collector):
    client = MagicMock()
    client.accounts = ["A-1", "A-2"]
    responses = {
        "A-1": reading_response([
            make_reading("0.40", "8.0", "2026-07-12T00:30:00+00:00"),
            make_reading("0.42", "8.1", "2026-07-12T01:00:00+00:00"),  # latest
        ]),
        "A-2": reading_response([
            make_reading("1.0", "20.0", "2026-07-12T00:30:00+00:00"),
        ]),
    }
    client.get_half_hour_reading.side_effect = lambda account: responses[account]
    collector._client = client

    families = {f.name: f for f in collector.collect()}

    assert _samples_by_account(families["oejp_half_hour_reading_kwh"]) == {
        "A-1": 0.42, "A-2": 1.0,
    }
    assert _samples_by_account(families["oejp_half_hour_cost_estimate_yen"]) == {
        "A-1": 8.1, "A-2": 20.0,
    }


def test_collect_emits_endat_timestamp_of_latest_reading(collector):
    from datetime import datetime

    client = MagicMock()
    client.accounts = ["A-1"]
    latest_end = "2026-07-12T01:00:00+00:00"
    client.get_half_hour_reading.return_value = reading_response([
        make_reading("0.40", "8.0", "2026-07-12T00:30:00+00:00"),
        make_reading("0.42", "8.1", latest_end),  # latest
    ])
    collector._client = client

    families = {f.name: f for f in collector.collect()}
    ts = _samples_by_account(families["oejp_half_hour_reading_timestamp_seconds"])
    assert ts == {"A-1": datetime.fromisoformat(latest_end).timestamp()}


def test_collect_skips_timestamp_when_endat_unparseable(collector):
    client = MagicMock()
    client.accounts = ["A-1"]
    client.get_half_hour_reading.return_value = reading_response([
        make_reading("0.42", "8.1", "not-a-timestamp"),
    ])
    collector._client = client

    families = {f.name: f for f in collector.collect()}
    # the reading value/cost are still reported; only the timestamp is omitted
    assert _samples_by_account(families["oejp_half_hour_reading_kwh"]) == {"A-1": 0.42}
    assert families["oejp_half_hour_reading_timestamp_seconds"].samples == []


def test_collect_populates_all_labels(collector):
    client = MagicMock()
    client.accounts = ["A-1"]
    client.get_half_hour_reading.return_value = reading_response(
        [make_reading("0.42", "8.1", "2026-07-12T01:00:00+00:00", rate_band="PEAK", step=3)],
        supply_details=make_supply_details(
            amperage="30", kva="6", kw="6.0", valid_from="2025-04-01T00:00:00+00:00"
        ),
    )
    collector._client = client

    families = {f.name: f for f in collector.collect()}
    labels = _labels_by_account(families["oejp_half_hour_reading_kwh"])["A-1"]
    assert labels == {
        "account": "A-1",
        "consumption_rate_band": "PEAK",
        "consumption_step": "3",
        "supply_amperage": "30",
        "supply_kva": "6",
        "supply_kw": "6.0",
        "supply_valid_from": "2025-04-01T00:00:00+00:00",
    }
    # cost series carries the same label set
    cost_labels = _labels_by_account(families["oejp_half_hour_cost_estimate_yen"])["A-1"]
    assert cost_labels == labels


def test_collect_uses_supply_details_from_the_winning_reading(collector):
    # two supply points with different hardware; the later reading wins and must
    # carry ITS point's supply details, not the other point's.
    client = MagicMock()
    client.accounts = ["A-1"]
    client.get_half_hour_reading.return_value = {
        "data": {
            "account": {
                "properties": [
                    {"electricitySupplyPoints": [
                        {
                            "supplyDetails": [make_supply_details(amperage="30", kva="6", kw="6.0")],
                            "halfHourlyReadings": [
                                make_reading("0.10", "2.0", "2026-07-12T00:30:00+00:00"),
                            ],
                        },
                        {
                            "supplyDetails": [make_supply_details(amperage="60", kva="12", kw="12.0")],
                            "halfHourlyReadings": [
                                make_reading("0.99", "9.0", "2026-07-12T02:00:00+00:00"),  # latest
                            ],
                        },
                    ]}
                ]
            }
        }
    }
    collector._client = client

    families = {f.name: f for f in collector.collect()}
    labels = _labels_by_account(families["oejp_half_hour_reading_kwh"])["A-1"]
    assert labels["supply_amperage"] == "60"
    assert labels["supply_kva"] == "12"
    assert labels["supply_kw"] == "12.0"


def test_collect_defaults_missing_supply_details_to_blank_labels(collector):
    client = MagicMock()
    client.accounts = ["A-1"]
    client.get_half_hour_reading.return_value = reading_response(
        [make_reading("0.42", "8.1", "2026-07-12T01:00:00+00:00")]  # no supplyDetails
    )
    collector._client = client

    families = {f.name: f for f in collector.collect()}
    labels = _labels_by_account(families["oejp_half_hour_reading_kwh"])["A-1"]
    assert labels["supply_amperage"] == ""
    assert labels["supply_kva"] == ""
    assert labels["supply_kw"] == ""
    assert labels["supply_valid_from"] == ""


def test_collect_picks_latest_across_multiple_supply_points(collector):
    client = MagicMock()
    client.accounts = ["A-1"]
    client.get_half_hour_reading.return_value = {
        "data": {
            "account": {
                "properties": [
                    {"electricitySupplyPoints": [
                        {"halfHourlyReadings": [
                            make_reading("0.10", "2.0", "2026-07-12T00:30:00+00:00"),
                        ]},
                        {"halfHourlyReadings": [
                            make_reading("0.99", "9.0", "2026-07-12T02:00:00+00:00"),
                        ]},
                    ]}
                ]
            }
        }
    }
    collector._client = client

    families = {f.name: f for f in collector.collect()}
    assert _samples_by_account(families["oejp_half_hour_reading_kwh"]) == {"A-1": 0.99}


class _AccountsBoom:
    """Stand-in client whose accounts lookup fails (e.g. API unreachable)."""

    @property
    def accounts(self):
        raise RuntimeError("api unreachable")


def test_collect_survives_accounts_failure(collector):
    collector._client = _AccountsBoom()

    # registration/scrape must not raise even if the backend is down
    families = {f.name: f for f in collector.collect()}
    assert families["oejp_half_hour_reading_kwh"].samples == []
    assert families["oejp_half_hour_cost_estimate_yen"].samples == []


def test_collect_skips_account_whose_reading_fetch_fails(collector):
    client = MagicMock()
    client.accounts = ["A-1", "A-2"]

    def fetch(account):
        if account == "A-1":
            raise RuntimeError("timeout")
        return reading_response([
            make_reading("1.0", "2.0", "2026-07-12T00:30:00+00:00"),
        ])

    client.get_half_hour_reading.side_effect = fetch
    collector._client = client

    families = {f.name: f for f in collector.collect()}
    # A-1 failed and is skipped; A-2 still reported
    assert _samples_by_account(families["oejp_half_hour_reading_kwh"]) == {"A-2": 1.0}


def test_collect_skips_accounts_without_readings(collector):
    client = MagicMock()
    client.accounts = ["A-1"]
    client.get_half_hour_reading.return_value = reading_response([])
    collector._client = client

    families = {f.name: f for f in collector.collect()}
    assert families["oejp_half_hour_reading_kwh"].samples == []
    assert families["oejp_half_hour_cost_estimate_yen"].samples == []
