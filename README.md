# Octopus Energy Japan (OEJP) Exporter

Not Affiliated with Octopus Energy in any way.

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
      - OEJP_EMAIL=oejp_email_address
      - OEJP_PASSWORD=oejp_password
    labels:
      - prometheus.io/scrape: "true"
      - prometheus.io/port: "9090"
```

## The Octopus Energy Japan (OEJP) Collector

Provide two consumption readings:
- oejp_half_hour_reading_kwh
- oejp_half_hour_cost_estimate_yen
- oejp_half_hour_reading_timestamp_seconds

Does not include the generated electricity.

With labels:
- account
- consumption_rate_band
- consumption_step
- supply_amperage
- supply_kva
- supply_kw
- supply_valid_from

Example data:

```bash
-> % curl -s localhost:9090|grep oejp
# HELP oejp_half_hour_reading_kwh Most recent half-hourly electricity consumption (kWh)
# TYPE oejp_half_hour_reading_kwh gauge
oejp_half_hour_reading_kwh{account="A-00000000",consumption_rate_band="CONSUMPTION_STEPPED_03_01",consumption_step="0",supply_amperage="40",supply_kva="None",supply_kw="None",supply_valid_from="****-**-**"} 0.2
# HELP oejp_half_hour_cost_estimate_yen Estimated cost of the most recent half-hourly reading
# TYPE oejp_half_hour_cost_estimate_yen gauge
oejp_half_hour_cost_estimate_yen{account="A-00000000",consumption_rate_band="CONSUMPTION_STEPPED_03_01",consumption_step="0",supply_amperage="40",supply_kva="None",supply_kw="None",supply_valid_from="****-**-**"} 5.26
# HELP oejp_half_hour_reading_timestamp_seconds Unix timestamp (endAt) of the most recent half-hourly reading
# TYPE oejp_half_hour_reading_timestamp_seconds gauge
oejp_half_hour_reading_timestamp_seconds{account="A-00000000",consumption_rate_band="CONSUMPTION_STEPPED_03_01",consumption_step="0",supply_amperage="40",supply_kva="None",supply_kw="None",supply_valid_from="****-**-**"} 1.78398e+09
```

## Trivia

While Home Assistant is great and there's at least one existing [HACS Integration](https://github.com/BottlecapDave/HomeAssistant-OctopusEnergy)
available. But I can't find one supporting the Japanese Octopus Energy API. So I started building one with basic promethues client.

The main drive for this I would like to know if something's consuming energy in my home, so I can have alerts based on 
current consumption and prediction. Currently I do not own any Solar Panels or Heat Pumps, so I did not include the generated electricity.

OEJP is providing half-hourly consumption data in time series format, so Prometheus is not the best fit for this. I had to
supply the latest one reading. OTLP with Clickhouse would be perfect for this. But I'll leave that to Claude.

Go would be a much better fit for this type of work, but I've used too much AI recently I wanted to write something 
with less AI like a practice. An exporter seems to be a very good fit. But I ended up involving Claude anyway.