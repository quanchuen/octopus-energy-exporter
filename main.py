#!/usr/bin/env python3

import logging
import os
import signal
import threading

from prometheus_client import REGISTRY, start_http_server

from oejp_exporter.client import DEFAULT_API_ENDPOINT
from oejp_exporter.metrics import OEJPCollector

log = logging.getLogger(__name__)


def build_collector(env=os.environ) -> OEJPCollector:
    """Construct the collector from environment configuration.

    Requires OEJP_EMAIL and OEJP_PASSWORD; OEJP_API_ENDPOINT is optional."""
    email = env.get("OEJP_EMAIL")
    password = env.get("OEJP_PASSWORD")
    if not (email and password):
        raise ValueError("OEJP_EMAIL and OEJP_PASSWORD must be set")
    return OEJPCollector(
        user_email=email,
        user_password=password,
        api_endpoint=env.get("OEJP_API_ENDPOINT", DEFAULT_API_ENDPOINT),
    )


def install_shutdown_handlers(stop_event: threading.Event) -> None:
    """Set the given event when a termination signal is received, so the main
    thread can shut down gracefully instead of being hard-killed."""
    def _handle(signum, _frame):
        log.info("received signal %s, shutting down", signal.Signals(signum).name)
        stop_event.set()

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)


def main(env=os.environ):
    logging.basicConfig(level=env.get("LOGGING_LEVEL", "INFO"))

    REGISTRY.register(build_collector(env))

    port = int(env.get("EXPORTER_PORT", "9090"))
    addr = env.get("EXPORTER_ADDR", "0.0.0.0")
    server, _thread = start_http_server(port=port, addr=addr)
    log.info("OEJP exporter listening on %s:%s", addr, port)

    stop = threading.Event()
    install_shutdown_handlers(stop)
    stop.wait()  # block until SIGINT/SIGTERM

    log.info("stopping HTTP server")
    server.shutdown()


if __name__ == "__main__":
    main()
