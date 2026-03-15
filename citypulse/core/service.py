from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from random import Random
from threading import Lock

from citypulse.core.models import (
    AnalyticsReport,
    CityKpi,
    CityOverview,
    CityStatus,
    DomainIncidentSummary,
    Incident,
    IncidentRecommendation,
    KpiTrend,
    SafetySnapshot,
    ServiceDomain,
    Severity,
    SimulationEvent,
    SnapshotBundle,
    TrendDirection,
    TransportSnapshot,
    UtilitiesSnapshot,
)


class CityDataService:
    """In-memory simulator for prototype workloads."""

    def __init__(
        self,
        seed: int = 42,
        history_hours: int = 48,
        tick_seconds: int = 6,
        max_open_incidents: int = 12,
        incident_min_interval_seconds: int = 10,
        incident_max_interval_seconds: int = 30,
    ) -> None:
        self._rng = Random(seed)
        self._history_hours = max(24, history_hours)
        self._tick_seconds = max(2, tick_seconds)
        self._max_open_incidents = max(4, max_open_incidents)
        self._incident_min_interval_seconds = max(5, incident_min_interval_seconds)
        self._incident_max_interval_seconds = max(
            self._incident_min_interval_seconds,
            incident_max_interval_seconds,
        )
        self._baseline = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        self._snapshots = [self._generate_snapshot(i) for i in range(self._history_hours)]
        self._incidents = self._generate_incidents()
        self._events: list[SimulationEvent] = []
        self._event_seq = 1
        self._incident_seq = 1100
        self._lock = Lock()
        self._last_tick = datetime.now(timezone.utc)
        self._next_incident_at = self._last_tick + timedelta(
            seconds=self._rng.randint(
                self._incident_min_interval_seconds,
                self._incident_max_interval_seconds,
            )
        )

        self._push_event(
            kind="simulator_started",
            message="Симулятор CityPulse запущен",
        )

    def latest_snapshot(self) -> SnapshotBundle:
        self._maybe_advance()
        return self._snapshots[-1]

    def snapshots_last_hours(self, hours: int) -> list[SnapshotBundle]:
        self._maybe_advance()
        if hours <= 0:
            return []
        window = min(hours, len(self._snapshots))
        return self._snapshots[-window:]

    def open_incidents(self, min_severity: Severity | None = None) -> list[Incident]:
        self._maybe_advance()
        incidents = [item for item in self._incidents if not item.resolved]
        if min_severity is None:
            return incidents
        order = [Severity.low, Severity.medium, Severity.high, Severity.critical]
        threshold_idx = order.index(min_severity)
        return [inc for inc in incidents if order.index(inc.severity) >= threshold_idx]

    def resolve_incident(self, incident_id: str) -> bool:
        self._maybe_advance()
        with self._lock:
            for incident in self._incidents:
                if incident.id == incident_id and not incident.resolved:
                    incident.resolved = True
                    self._push_event(
                        kind="incident_resolved_manual",
                        message=f"Инцидент вручную закрыт оператором: {incident.id}",
                        domain=incident.domain,
                        severity=incident.severity,
                    )
                    self._append_evolved_snapshot()
                    self._prune_events()
                    return True
        return False

    def recent_events(self, limit: int = 20, active_seconds: int = 180) -> list[SimulationEvent]:
        self._maybe_advance()
        now = datetime.now(timezone.utc)
        max_age = timedelta(seconds=max(10, active_seconds))
        active = [item for item in self._events if now - item.created_at <= max_age]
        return active[-limit:]

    def city_overview(self) -> CityOverview:
        self._maybe_advance()
        latest = self._snapshots[-1]
        open_items = self._open_incidents_unsafe()
        critical_count = sum(1 for item in open_items if item.severity == Severity.critical)
        status = self._build_city_status(latest.kpi.city_pulse_index, critical_count)
        top_risks = self._top_risks(latest, open_items)
        return CityOverview(
            timestamp=latest.timestamp,
            status=status,
            city_pulse_index=latest.kpi.city_pulse_index,
            open_incidents=len(open_items),
            critical_incidents=critical_count,
            top_risks=top_risks,
        )

    def kpi_trends(self, hours: int) -> list[KpiTrend]:
        self._maybe_advance()
        snapshots = self.snapshots_last_hours(max(2, hours))
        first = snapshots[0].kpi
        last = snapshots[-1].kpi
        return [
            self._build_trend("mobility_score", first.mobility_score, last.mobility_score),
            self._build_trend("reliability_score", first.reliability_score, last.reliability_score),
            self._build_trend("safety_score", first.safety_score, last.safety_score),
            self._build_trend("city_pulse_index", first.city_pulse_index, last.city_pulse_index),
        ]

    def analytics_report(self, hours: int) -> AnalyticsReport:
        self._maybe_advance()
        snapshots = self.snapshots_last_hours(hours)
        indexes = [item.kpi.city_pulse_index for item in snapshots]
        open_items = self._open_incidents_unsafe()
        pressure = []
        for domain in ServiceDomain:
            domain_items = [item for item in open_items if item.domain == domain]
            pressure.append(
                DomainIncidentSummary(
                    domain=domain,
                    open_count=len(domain_items),
                    critical_count=sum(1 for item in domain_items if item.severity == Severity.critical),
                )
            )

        trend = TrendDirection.stable
        if len(indexes) >= 2:
            trend = self._resolve_direction(indexes[-1] - indexes[0])

        return AnalyticsReport(
            window_hours=len(snapshots),
            average_index=round(sum(indexes) / len(indexes), 2),
            min_index=round(min(indexes), 2),
            max_index=round(max(indexes), 2),
            trend=trend,
            domain_pressure=pressure,
        )

    def incident_recommendations(self, min_severity: Severity | None = None) -> list[IncidentRecommendation]:
        self._maybe_advance()
        open_items = self.open_incidents(min_severity=min_severity)
        return [self._build_recommendation(item) for item in open_items]

    def _maybe_advance(self) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            elapsed = (now - self._last_tick).total_seconds()
            if elapsed < self._tick_seconds:
                return
            steps = min(3, int(elapsed // self._tick_seconds))
            for _ in range(steps):
                self._simulate_step()
            self._last_tick = self._last_tick + timedelta(seconds=steps * self._tick_seconds)
            if (now - self._last_tick).total_seconds() > self._tick_seconds:
                self._last_tick = now

    def _simulate_step(self) -> None:
        now = datetime.now(timezone.utc)
        open_items = self._open_incidents_unsafe()

        if now >= self._next_incident_at:
            if len(open_items) < self._max_open_incidents:
                new_incident = self._create_incident(now)
                self._incidents.append(new_incident)
                self._push_event(
                    kind="incident_created",
                    message=f"Новый инцидент: {new_incident.description}",
                    domain=new_incident.domain,
                    severity=new_incident.severity,
                )
            self._schedule_next_incident(now)

        open_items = self._open_incidents_unsafe()
        if len(open_items) > 2 and self._rng.random() < 0.40:
            to_resolve = sorted(open_items, key=lambda item: item.created_at)[0]
            to_resolve.resolved = True
            self._push_event(
                kind="incident_resolved",
                message=f"Инцидент закрыт: {to_resolve.id}",
                domain=to_resolve.domain,
                severity=to_resolve.severity,
            )

        self._append_evolved_snapshot()
        self._prune_events()

    def _schedule_next_incident(self, from_ts: datetime) -> None:
        delay = self._rng.randint(
            self._incident_min_interval_seconds,
            self._incident_max_interval_seconds,
        )
        self._next_incident_at = from_ts + timedelta(seconds=delay)

    def _append_evolved_snapshot(self) -> None:
        prev = self._snapshots[-1]
        open_items = self._open_incidents_unsafe()
        critical_open = sum(1 for item in open_items if item.severity == Severity.critical)

        transport = TransportSnapshot(
            avg_delay_min=round(self._clamp(prev.transport.avg_delay_min + self._rng.uniform(-0.9, 1.1), 1.0, 22.0), 2),
            active_vehicles=int(self._clamp(prev.transport.active_vehicles + self._rng.randint(-12, 12), 280, 760)),
            congestion_index=round(self._clamp(prev.transport.congestion_index + self._rng.uniform(-0.05, 0.06), 0.05, 0.98), 2),
        )

        next_outages = self._next_outages(prev.utilities.outages_count)
        next_energy = self._next_energy(prev.utilities.energy_load_mw, next_outages)
        next_pressure = self._next_water_pressure(prev.utilities.water_pressure, next_outages)

        utilities = UtilitiesSnapshot(
            water_pressure=round(next_pressure, 2),
            outages_count=next_outages,
            energy_load_mw=round(next_energy, 1),
        )
        safety = SafetySnapshot(
            incidents_open=len(open_items),
            avg_response_min=round(self._clamp(prev.safety.avg_response_min + self._rng.uniform(-0.8, 0.9) + critical_open * 0.1, 3.0, 24.0), 2),
            cameras_online_pct=round(self._clamp(prev.safety.cameras_online_pct + self._rng.uniform(-0.6, 0.4), 80, 100), 2),
        )
        kpi = self._build_kpi(transport, utilities, safety)

        self._snapshots.append(
            SnapshotBundle(
                timestamp=datetime.now(timezone.utc),
                transport=transport,
                utilities=utilities,
                safety=safety,
                kpi=kpi,
            )
        )
        if len(self._snapshots) > self._history_hours:
            self._snapshots = self._snapshots[-self._history_hours :]

    def _next_outages(self, current: int) -> int:
        if current >= 14:
            delta = self._rng.randint(-3, 0)
        elif current <= 4:
            delta = self._rng.randint(0, 2)
        else:
            delta = self._rng.randint(-2, 2)
        return int(self._clamp(current + delta, 0, 20))

    def _next_energy(self, current: float, outages: int) -> float:
        target = 690.0
        reversion = (target - current) * 0.18
        noise = self._rng.uniform(-22.0, 22.0)
        value = current + reversion + noise
        if outages > 12:
            value += self._rng.uniform(6.0, 18.0)
        elif outages < 4:
            value -= self._rng.uniform(0.0, 8.0)
        return self._clamp(value, 360.0, 920.0)

    def _next_water_pressure(self, current: float, outages: int) -> float:
        target = 3.4
        reversion = (target - current) * 0.22
        noise = self._rng.uniform(-0.11, 0.11)
        penalty = 0.0
        if outages > 12:
            penalty = self._rng.uniform(0.04, 0.14)
        return self._clamp(current + reversion + noise - penalty, 1.8, 4.8)

    def _create_incident(self, now: datetime) -> Incident:
        self._incident_seq += 1
        domain = self._rng.choice(list(ServiceDomain))
        severity = self._rng.choices(
            [Severity.low, Severity.medium, Severity.high, Severity.critical],
            weights=[0.2, 0.42, 0.28, 0.10],
            k=1,
        )[0]
        templates = {
            ServiceDomain.transport: [
                "Сбой приоритета светофорного цикла",
                "Резкое увеличение задержек на магистрали",
                "Отклонение маршрутов общественного транспорта",
            ],
            ServiceDomain.utilities: [
                "Локальное падение давления в магистрали",
                "Перегрузка подстанции в жилом секторе",
                "Аварийное отключение квартальной линии",
            ],
            ServiceDomain.safety: [
                "Рост очереди экстренных вызовов",
                "Частичная недоступность камер наблюдения",
                "Сложный инцидент в центральном районе",
            ],
        }
        return Incident(
            id=f"INC-{self._incident_seq}",
            domain=domain,
            severity=severity,
            description=self._rng.choice(templates[domain]),
            created_at=now,
            resolved=False,
        )

    def _push_event(
        self,
        kind: str,
        message: str,
        domain: ServiceDomain | None = None,
        severity: Severity | None = None,
    ) -> None:
        event = SimulationEvent(
            id=f"EV-{self._event_seq}",
            kind=kind,
            message=message,
            created_at=datetime.now(timezone.utc),
            domain=domain,
            severity=severity,
        )
        self._event_seq += 1
        self._events.append(event)

    def _prune_events(self) -> None:
        now = datetime.now(timezone.utc)
        ttl = timedelta(minutes=6)
        self._events = [item for item in self._events if now - item.created_at <= ttl]
        if len(self._events) > 200:
            self._events = self._events[-200:]

    def _open_incidents_unsafe(self) -> list[Incident]:
        return [item for item in self._incidents if not item.resolved]

    def _generate_snapshot(self, offset_hour: int) -> SnapshotBundle:
        ts = self._baseline - timedelta(hours=(self._history_hours - 1 - offset_hour))
        transport = TransportSnapshot(
            avg_delay_min=round(self._rng.uniform(2.5, 12.0), 2),
            active_vehicles=self._rng.randint(350, 600),
            congestion_index=round(self._rng.uniform(0.15, 0.85), 2),
        )
        utilities = UtilitiesSnapshot(
            water_pressure=round(self._rng.uniform(2.5, 4.2), 2),
            outages_count=self._rng.randint(0, 16),
            energy_load_mw=round(self._rng.uniform(420, 900), 1),
        )
        safety = SafetySnapshot(
            incidents_open=self._rng.randint(3, 40),
            avg_response_min=round(self._rng.uniform(4.0, 18.0), 2),
            cameras_online_pct=round(self._rng.uniform(88, 99.8), 2),
        )
        kpi = self._build_kpi(transport, utilities, safety)
        return SnapshotBundle(
            timestamp=ts,
            transport=transport,
            utilities=utilities,
            safety=safety,
            kpi=kpi,
        )

    def _build_kpi(
        self,
        transport: TransportSnapshot,
        utilities: UtilitiesSnapshot,
        safety: SafetySnapshot,
    ) -> CityKpi:
        mobility_score = max(0.0, 100 - transport.avg_delay_min * 4 - transport.congestion_index * 35)
        reliability_score = max(
            0.0,
            min(
                100.0,
                100
                - utilities.outages_count * 3.2
                - max(0, utilities.energy_load_mw - 820) / 6.0
                - abs(utilities.water_pressure - 3.4) * 6.0,
            ),
        )
        safety_score = max(0.0, 100 - safety.incidents_open * 1.6 - safety.avg_response_min * 2.5)
        city_pulse_index = (mobility_score + reliability_score + safety_score) / 3
        return CityKpi(
            mobility_score=round(mobility_score, 2),
            reliability_score=round(reliability_score, 2),
            safety_score=round(safety_score, 2),
            city_pulse_index=round(city_pulse_index, 2),
        )

    def _build_trend(self, metric: str, previous: float, current: float) -> KpiTrend:
        delta = current - previous
        return KpiTrend(
            metric=metric,
            current=round(current, 2),
            previous=round(previous, 2),
            delta=round(delta, 2),
            direction=self._resolve_direction(delta),
        )

    def _resolve_direction(self, delta: float) -> TrendDirection:
        if delta > 1.0:
            return TrendDirection.up
        if delta < -1.0:
            return TrendDirection.down
        return TrendDirection.stable

    def _build_city_status(self, city_index: float, critical_incidents: int) -> CityStatus:
        if city_index < 45 or critical_incidents >= 2:
            return CityStatus.critical
        if city_index < 65 or critical_incidents >= 1:
            return CityStatus.warning
        return CityStatus.normal

    def _top_risks(self, latest: SnapshotBundle, open_items: list[Incident]) -> list[str]:
        risks: list[str] = []
        if latest.transport.congestion_index > 0.65:
            risks.append("Высокая загруженность дорожной сети")
        if latest.utilities.outages_count > 10:
            risks.append("Рост аварий в коммунальной инфраструктуре")
        if latest.safety.avg_response_min > 12:
            risks.append("Увеличено время реагирования экстренных служб")
        if any(item.severity == Severity.critical for item in open_items):
            risks.append("Есть критические инциденты, требуется эскалация")
        if not risks:
            risks.append("Критических рисков на текущий момент не выявлено")
        return risks

    def _build_recommendation(self, incident: Incident) -> IncidentRecommendation:
        mapping = {
            ServiceDomain.transport: (
                "Центр управления движением",
                ["Перевести светофоры в резервный режим", "Перенаправить потоки общественного транспорта"],
            ),
            ServiceDomain.utilities: (
                "Аварийная служба ЖКХ",
                ["Локализовать участок аварии", "Выполнить переключение на резервную линию"],
            ),
            ServiceDomain.safety: (
                "Единый центр реагирования 112",
                ["Усилить дежурные смены", "Запустить межведомственную координацию"],
            ),
        }
        recommended_team, actions = mapping[incident.domain]
        severity_sla = {
            Severity.low: 180,
            Severity.medium: 90,
            Severity.high: 45,
            Severity.critical: 20,
        }
        return IncidentRecommendation(
            incident_id=incident.id,
            severity=incident.severity,
            domain=incident.domain,
            recommended_team=recommended_team,
            sla_minutes=severity_sla[incident.severity],
            actions=actions,
        )

    def _generate_incidents(self) -> list[Incident]:
        now = self._baseline
        return [
            Incident(
                id="INC-1001",
                domain=ServiceDomain.transport,
                severity=Severity.high,
                description="Signal controller outage on central junction",
                created_at=now - timedelta(minutes=35),
                resolved=False,
            ),
            Incident(
                id="INC-1002",
                domain=ServiceDomain.utilities,
                severity=Severity.medium,
                description="Water pressure drop in district 7",
                created_at=now - timedelta(hours=2, minutes=10),
                resolved=False,
            ),
            Incident(
                id="INC-1003",
                domain=ServiceDomain.safety,
                severity=Severity.critical,
                description="Emergency response overload in downtown sector",
                created_at=now - timedelta(minutes=12),
                resolved=False,
            ),
            Incident(
                id="INC-0995",
                domain=ServiceDomain.utilities,
                severity=Severity.low,
                description="Planned maintenance completed",
                created_at=now - timedelta(hours=10),
                resolved=True,
            ),
        ]

    def _clamp(self, value: float, left: float, right: float) -> float:
        return max(left, min(right, value))


service = CityDataService(
    seed=int(os.getenv("CITYPULSE_SEED", "42")),
    history_hours=int(os.getenv("CITYPULSE_HISTORY_HOURS", "48")),
    tick_seconds=int(os.getenv("CITYPULSE_TICK_SECONDS", "6")),
    max_open_incidents=int(os.getenv("CITYPULSE_MAX_OPEN_INCIDENTS", "12")),
    incident_min_interval_seconds=int(os.getenv("CITYPULSE_INCIDENT_MIN_INTERVAL_SECONDS", "10")),
    incident_max_interval_seconds=int(os.getenv("CITYPULSE_INCIDENT_MAX_INTERVAL_SECONDS", "30")),
)
