import time

from fastapi.testclient import TestClient

from citypulse.main import app


client = TestClient(app)


def benchmark(path: str, iterations: int = 1000) -> tuple[float, float]:
    start = time.perf_counter()
    for _ in range(iterations):
        response = client.get(path)
        if response.status_code != 200:
            raise RuntimeError(f"Unexpected status for {path}: {response.status_code}")
    elapsed = time.perf_counter() - start
    avg_ms = elapsed * 1000 / iterations
    rps = iterations / elapsed
    return avg_ms, rps


if __name__ == "__main__":
    endpoints = [
        "/health",
        "/v1/snapshots/latest",
        "/v1/snapshots?hours=6",
        "/v1/incidents/open?min_severity=high",
        "/v1/events/recent?limit=20&active_seconds=180",
        "/v1/analytics/overview",
        "/v1/analytics/report?hours=12",
    ]
    print("CityPulse API benchmark (in-process)")
    for endpoint in endpoints:
        avg_ms, rps = benchmark(endpoint)
        print(f"{endpoint:42} avg={avg_ms:7.3f} ms  rps={rps:8.1f}")
