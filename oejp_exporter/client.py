import datetime

import requests
import logging
import os

from .oejp_gql_queries import GET_ACCOUNT_BODY, AUTH_BODY, GET_HALF_HOUR_USAGE

DEFAULT_API_ENDPOINT = "https://api.oejp-kraken.energy/v1/graphql/"


class OEJPClient:
    # Refresh the token this many seconds before its real expiry, to avoid
    # racing a token that expires mid-request (clock skew / network latency).
    _EXPIRY_SKEW = datetime.timedelta(seconds=30)

    def __init__(self,
                 user_email: str,
                 user_password: str,
                 api_endpoint: str = DEFAULT_API_ENDPOINT,
                 logging_level: str = "INFO"
                 ):
        super().__init__()
        self._email = user_email
        self._password = user_password
        self._api_endpoint = api_endpoint
        self._logging_level = logging_level


        self._session = None
        self._accounts = None
        self._logger = None

        self._token = None
        self._token_expiry = None
        self._refresh_token = None
        self._refresh_expiry = None


    @property
    def log(self) -> logging.Logger:
        if not self._logger:
            self._logger = logging.getLogger()
            self._logger.setLevel(os.environ.get("LOGGING_LEVEL", self._logging_level))
        return self._logger

    @staticmethod
    def _now() -> datetime.datetime:
        return datetime.datetime.now(datetime.UTC)

    def _store_refresh_token(self, refresh_token, refresh_expires_in) -> None:
        self._refresh_token = refresh_token
        self._refresh_expiry = (
            self._now() + datetime.timedelta(seconds=refresh_expires_in)
            if refresh_expires_in is not None else None
        )

    def _obtain_token(self, credentials: dict) -> str:
        """Call obtainKrakenToken with the given input (credentials or a
        refresh token) and store the resulting token and its lifecycle state."""
        body = {
            "query": AUTH_BODY,
            "variables": {"input": credentials},
        }
        resp = requests.post(url=self._api_endpoint, json=body)
        resp.raise_for_status()
        result = resp.json().get("data", {}).get("obtainKrakenToken", {}) or {}

        token = result.get("token", "")
        if not token:
            raise ValueError("Failed to get token from OEJP")

        self._token = token
        exp = result.get("payload", {}).get("exp")
        self._token_expiry = (
            datetime.datetime.fromtimestamp(exp, tz=datetime.UTC) if exp else None
        )

        self._store_refresh_token(
            result.get("refreshToken"), result.get("refreshExpiresIn")
        )
        return token

    def _reauthenticate(self) -> str:
        if not (self._email and self._password):
            raise ValueError("Authorization detail not set")
        self.log.info("authenticating with credentials")
        return self._obtain_token({"email": self._email, "password": self._password})

    def _refresh(self) -> str:
        self.log.info("refreshing token with refresh token")
        return self._obtain_token({"refreshToken": self._refresh_token})

    def authenticate(self) -> str:
        """Obtain a token from scratch using the configured credentials."""
        return self._reauthenticate()

    def _is_expired(self, expiry: datetime.datetime | None) -> bool:
        # No recorded expiry means we cannot trust the token/refresh token.
        if expiry is None:
            return True
        return self._now() >= expiry - self._EXPIRY_SKEW

    @property
    def token(self) -> str:
        if self._token and not self._is_expired(self._token_expiry):
            return self._token

        if self._refresh_token and not self._is_expired(self._refresh_expiry):
            try:
                return self._refresh()
            except Exception:
                self.log.warning("token refresh failed; re-authenticating", exc_info=True)

        return self._reauthenticate()

    @property
    def session(self) -> requests.Session:
        if not self._session:
            self._session = requests.session()

        return self._session

    @property
    def accounts(self) -> list[str]:
        if not self._accounts:
            body = {
                "query": GET_ACCOUNT_BODY
            }
            resp = self.session.post(url=self._api_endpoint, json=body, headers={"authorization": f"JWT {self.token}"})
            resp.raise_for_status()
            data = resp.json()
            accounts = [n.get('number',"") for n in data.get("data", {}).get("viewer",{}).get("accounts",[{}])]
            if not any(accounts):
                self.log.warning("cannot get all accounts for the given user")
            if not all(accounts):
                raise ValueError("cannot get accounts")
            self._accounts = accounts
        return self._accounts

    def get_half_hour_reading(self,
                              account_number: str,
                              from_datetime: datetime.datetime | None = None,
                              to_datetime: datetime.datetime | None = None):
        if to_datetime is None:
            to_datetime = self._now()
        if from_datetime is None:
            from_datetime = to_datetime - datetime.timedelta(hours=24)
        body = {
            "query": GET_HALF_HOUR_USAGE,
            "variables": {
                "accountNumber": account_number,
                "fromDatetime": from_datetime.isoformat(),
                "toDatetime": to_datetime.isoformat(),
            },
        }
        ret = self.session.post(url=self._api_endpoint, json=body, headers={"authorization": f"JWT {self.token}"})
        ret.raise_for_status()
        return ret.json()


if __name__ == '__main__':
    logging.basicConfig()
    email = os.environ.get("OEJP_EMAIL")
    password = os.environ.get("OEJP_PASSWORD")
    client = OEJPClient(user_email=email, user_password=password)
    print(client.accounts)

