from prometheus_client import start_http_server

def main():
    resource = Resource.create(attributes={
        SERVICE_NAME: "oejp-consumer-exporter"
    })
    reader = PrometheusMetricReader()
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(provider)
    start_http_server(port=9090, addr="localhost")



if __name__ == "__main__":
    main()
