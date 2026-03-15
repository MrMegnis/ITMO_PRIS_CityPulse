from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse

from citypulse.core.models import AnalyticsReport, CityOverview, KpiTrend, Severity, SimulationEvent
from citypulse.core.service import service

router = APIRouter()
_UI_INDEX = Path(__file__).resolve().parent.parent / "ui" / "index.html"


@router.get("/")
def root_redirect():
    return RedirectResponse(url="/ui")


@router.get("/ui")
def ui_page():
    return FileResponse(_UI_INDEX)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/v1/snapshots/latest")
def latest_snapshot():
    return service.latest_snapshot()


@router.get("/v1/snapshots")
def snapshots(hours: int = Query(default=6, ge=1, le=168)):
    return service.snapshots_last_hours(hours)


@router.get("/v1/incidents/open")
def incidents_open(min_severity: Severity | None = Query(default=None)):
    return service.open_incidents(min_severity=min_severity)


@router.post("/v1/incidents/{incident_id}/resolve")
def incidents_resolve(incident_id: str):
    if not service.resolve_incident(incident_id):
        raise HTTPException(status_code=404, detail="Incident not found or already resolved")
    return {"status": "resolved", "incident_id": incident_id}


@router.get("/v1/incidents/recommendations")
def incidents_recommendations(min_severity: Severity | None = Query(default=None)):
    return service.incident_recommendations(min_severity=min_severity)


@router.get("/v1/events/recent", response_model=list[SimulationEvent])
def events_recent(limit: int = Query(default=20, ge=1, le=100), active_seconds: int = Query(default=180, ge=15, le=900)):
    return service.recent_events(limit=limit, active_seconds=active_seconds)


@router.get("/v1/analytics/overview", response_model=CityOverview)
def analytics_overview():
    return service.city_overview()


@router.get("/v1/analytics/trends", response_model=list[KpiTrend])
def analytics_trends(hours: int = Query(default=6, ge=2, le=168)):
    return service.kpi_trends(hours=hours)


@router.get("/v1/analytics/report", response_model=AnalyticsReport)
def analytics_report(hours: int = Query(default=12, ge=2, le=168)):
    return service.analytics_report(hours=hours)
