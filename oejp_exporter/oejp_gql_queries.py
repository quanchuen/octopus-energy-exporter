# https://github.com/octoenergy/oejp-api-example/blob/56533268988d44015489f693c215333f2208c1de/octopus.py

AUTH_BODY = """
mutation obtainKrakenToken($input: ObtainJSONWebTokenInput!) {
  obtainKrakenToken(input: $input) {
    refreshToken
    refreshExpiresIn
    payload
    token
  }
}
"""

GET_ACCOUNT_BODY = """
query accountViewer {
  viewer {
    accounts {
      number
    }
  }
}
"""

GET_HALF_HOUR_USAGE = """
query OEJP_HalfHourReadings($accountNumber: String!, $fromDatetime: DateTime, $toDatetime: DateTime) {
  account(accountNumber: $accountNumber) {
    number
    properties {
      electricitySupplyPoints {
        halfHourlyReadings(fromDatetime: $fromDatetime, toDatetime: $toDatetime) {
          consumptionRateBand
          consumptionStep
          costEstimate
          version
          value
          endAt
          startAt
        }
        supplyDetails {
          amperage
          kva
          kw
          validFrom
        }
      }
    }
  }
}
"""