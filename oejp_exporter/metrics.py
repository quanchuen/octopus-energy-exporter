import logging

from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector

from .client import OEJPClient

log = logging.getLogger(__name__)


class OEJPCollector(Collector):
    def __init__(self,
                 user_email: str,
                 user_password: str,
                 api_endpoint: str
                 ):
        self._client = None
        self._user_email = user_email
        self._user_password = user_password
        self._api_endpoint = api_endpoint

    @property
    def client(self) -> OEJPClient:
        if not self._client:
            self._client = OEJPClient(
                user_email=self._user_email,
                user_password=self._user_password,
                api_endpoint=self._api_endpoint,
            )
        return self._client

    @staticmethod
    def _latest_reading(response: dict) -> dict | None:
        account = response.get("data", {}).get("account", {}) or {}
        readings = [
            {
                **reading,
                "supplyDetails": point.get("supplyDetails", [{}])[0],
            }
            for prop in account.get("properties", []) or []
            for point in prop.get("electricitySupplyPoints", []) or []
            for reading in point.get("halfHourlyReadings", []) or []
        ]
        if not readings:
            return None
        # endAt is an ISO-8601 in string
        return max(readings, key=lambda r: r.get("endAt", ""))

    def collect(self):
        kwh = GaugeMetricFamily(
            "oejp_half_hour_reading_kwh",
            "Most recent half-hourly electricity consumption (kWh)",
            labels=["account", "consumption_rate_band", "consumption_step", "supply_amperage", "supply_kva", "supply_kw", "supply_valid_from"],
        )
        cost = GaugeMetricFamily(
            "oejp_half_hour_cost_estimate_yen",
            "Estimated cost of the most recent half-hourly reading",
            labels=["account", "consumption_rate_band", "consumption_step", "supply_amperage", "supply_kva", "supply_kw", "supply_valid_from"],
        )

        try:
            accounts = self.client.accounts
        except Exception:
            log.warning("failed to fetch accounts", exc_info=True)
            accounts = []

        for account in accounts:
            try:
                reading = self._latest_reading(
                    self.client.get_half_hour_reading(account)
                )
            except Exception:
                log.warning("failed to fetch readings for %s", account, exc_info=True)
                continue
            if reading is None:
                continue

            supply_details = reading.get("supplyDetails", {})
            labels = [
                account,
                reading.get("consumptionRateBand", ""),
                str(reading.get("consumptionStep", "")),
                str(supply_details.get("amperage", "")),
                str(supply_details.get("kva", "")),
                str(supply_details.get("kw", "")),
                supply_details.get("validFrom", ""),
            ]
            kwh.add_metric(labels, float(reading["value"]))
            cost.add_metric(labels, float(reading["costEstimate"]))

        yield kwh
        yield cost
