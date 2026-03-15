from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ServiceDomain(str, Enum):
    transport = "transport"
    utilities = "utilities"
    safety = "safety"


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class TrendDirection(str, Enum):
    up = "up"
    down = "down"
    stable = "stable"


class CityStatus(str, Enum):
    normal = "normal"
    warning = "warning"
    critical = "critical"


class TransportSnapshot(BaseModel):
    avg_delay_min: float = Field(ge=0)
    active_vehicles: int = Field(ge=0)
    congestion_index: float = Field(ge=0, le=1)


class UtilitiesSnapshot(BaseModel):
    water_pressure: float = Field(ge=0)
    outages_count: int = Field(ge=0)
    energy_load_mw: float = Field(ge=0)


class SafetySnapshot(BaseModel):
    incidents_open: int = Field(ge=0)
    avg_response_min: float = Field(ge=0)
    cameras_online_pct: float = Field(ge=0, le=100)


class Incident(BaseModel):
    id: str
    domain: ServiceDomain
    severity: Severity
    description: str
    created_at: datetime
    resolved: bool = False


class CityKpi(BaseModel):
    mobility_score: float = Field(ge=0, le=100)
    reliability_score: float = Field(ge=0, le=100)
    safety_score: float = Field(ge=0, le=100)
    city_pulse_index: float = Field(ge=0, le=100)


class SnapshotBundle(BaseModel):
    timestamp: datetime
    transport: TransportSnapshot
    utilities: UtilitiesSnapshot
    safety: SafetySnapshot
    kpi: CityKpi


class KpiTrend(BaseModel):
    metric: str
    current: float
    previous: float
    delta: float
    direction: TrendDirection


class DomainIncidentSummary(BaseModel):
    domain: ServiceDomain
    open_count: int = Field(ge=0)
    critical_count: int = Field(ge=0)


class AnalyticsReport(BaseModel):
    window_hours: int = Field(ge=1)
    average_index: float = Field(ge=0, le=100)
    min_index: float = Field(ge=0, le=100)
    max_index: float = Field(ge=0, le=100)
    trend: TrendDirection
    domain_pressure: list[DomainIncidentSummary]


class IncidentRecommendation(BaseModel):
    incident_id: str
    severity: Severity
    domain: ServiceDomain
    recommended_team: str
    sla_minutes: int = Field(ge=1)
    actions: list[str]


class CityOverview(BaseModel):
    timestamp: datetime
    status: CityStatus
    city_pulse_index: float = Field(ge=0, le=100)
    open_incidents: int = Field(ge=0)
    critical_incidents: int = Field(ge=0)
    top_risks: list[str]


class SimulationEvent(BaseModel):
    id: str
    kind: str
    message: str
    created_at: datetime
    domain: ServiceDomain | None = None
    severity: Severity | None = None
