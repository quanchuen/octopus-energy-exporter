import datetime

import requests
import logging
import os

from .oejp_gql_queries import GET_ACCOUNT_BODY, AUTH_BODY, GET_HALF_HOUR_USAGE


class OEJPClient:
    # TODO(quan): handle session refresh
    def __init__(self,
                 user_email: str,
                 user_password: str,
                 api_endpoint: str = "https://api.oejp-kraken.energy/v1/graphql/",
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


    @property
    def log(self) -> logging.Logger:
        if not self._logger:
            self._logger = logging.getLogger()
            self._logger.setLevel(os.environ.get("LOGGING_LEVEL", self._logging_level))
        return self._logger

    def authenticate(self):

        if not (self._email or self._password):
            raise ValueError("Authorization detail not set")
        body = {
            "query": AUTH_BODY,
            "variables": {
                "input": {"email": self._email, "password": self._password}
            }
        }
        resp = requests.post(url = self._api_endpoint, json=body)
        resp.raise_for_status()
        data = resp.json()
        payload = data.get("data",{}).get("obtainKrakenToken",{})
        _token = payload.get("token", "")
        self._token
        if not _token:
            raise ValueError("Failed to get token from OEJP")
        self._refresh_token = payload["refresh_token"]
        return _token

    @property
    def token(self):
        if not self._token:
            self._token = self.authenticate()

        return self._token

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

    def get_half_hour_reading(self):
        ret = self.session.post(url=self._api_endpoint, json=GET_HALF_HOUR_USAGE, headers={"authorization": f"JWT {self.token}"})
        ret.raise_for_status()
        return ret.json()


if __name__ == '__main__':
    logging.basicConfig()
    email = os.environ.get("OEJP_EMAIL")
    password = os.environ.get("OEJP_PASSWORD")
    client = OEJPClient(user_email=email, user_password=password)
    print(client.accounts)

