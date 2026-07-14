# Octopus Energy Japan (OEJP) Exporter

A very basic Prometheus exporter for Octopus Energy Japan.

Fetches half-hour usage from Octopus Energy API and exposes it as Prometheus metrics. From the [Official GraphQL API](https://api.oejp-kraken.energy/v1/graphql/)

As the name suggests, you have to be a customer of Octopus Energy (Japan). This records only consumption, not the 
generated electricity.

## Installation and Usage

Using with prometheus container, for example:

```yaml
version: '3'
services:
  prometheus:
    image: "prom/prometheus:latest"
    # ...
    volumes:
      # Docker Api socket, I'm using rootless, so it's
      - /run/user/1000/docker.sock:/var/run/docker.sock
      # Or with root
      - /run/docker.sock:/var/run/docker.sock:ro
  oejp-exporter:
    build: .
    environment:
      - OEJP_EMAIL=your_account_number
      - OEJP_PASSWORD=your_api_key
    labels:
      - prometheus.io/scrape: "true"
      - prometheus.io/port: "9090"
```

## The Octopus Energy Japan (OEJP) Collector

Provide two consumption readings:
- oejp_half_hour_reading_kwh
- oejp_half_hour_cost_estimate_yen

Does not include the generated electricity.

With labels:
- account
- consumption_rate_band
- consumption_step
- supply_amperage
- supply_kva
- supply_kw
- supply_valid_from

## Trivia

While Home Assistant is great and there's at least one existing [HACS Integration](https://github.com/BottlecapDave/HomeAssistant-OctopusEnergy)
available. But I can't find one supporting the Japanese Octopus Energy API. So I started building one with basic promethues client.

The main drive for this I would like to know if something's consuming energy in my home, so I can have alerts based on 
current consumption and prediction. Currently I do not own any Solar Panels or Heat Pumps, so I did not include the generated electricity.

OEJP is providing half-hourly consumption data in time series format, so Prometheus is not the best fit for this. I had to
supply the latest one reading. OTLP with Clickhouse would be perfect for this. But I'll leave that to Claude.