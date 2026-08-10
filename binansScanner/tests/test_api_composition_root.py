from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from api.api_router import ApiRouter
from api.api_service import ApiService
from core.dependency_container import DependencyContainer
from core.pipeline import Pipeline
from scheduler.scheduler_jobs import RegisteredJob
from scheduler.scheduler_models import ScheduledJob, SchedulerState
from scheduler.scheduler_service import SchedulerService


class TestApiCompositionRoot(unittest.TestCase):
    def setUp(self) -> None:
        self.container = DependencyContainer()

    def tearDown(self) -> None:
        self.container.reset()

    def test_scheduler_is_owned_by_composition_root(self) -> None:
        scheduler = self.container.build_scheduler_service()

        self.assertIsInstance(scheduler, SchedulerService)
        self.assertIs(scheduler, self.container.build_scheduler_service())

    def test_api_service_reuses_container_scheduler(self) -> None:
        scheduler = self.container.build_scheduler_service()
        service = self.container.build_api_service()

        self.assertIsInstance(service, ApiService)
        self.assertIs(service._scheduler, scheduler)
        self.assertIs(service, self.container.build_api_service())

    def test_api_service_reuses_container_pipeline(self) -> None:
        pipeline = self.container.build_pipeline()
        service = self.container.build_api_service()

        self.assertIsInstance(pipeline, Pipeline)
        self.assertIs(service._pipeline, pipeline)
        self.assertIs(service._pipeline, self.container.build_pipeline())

    def test_api_router_reuses_container_api_service(self) -> None:
        service = self.container.build_api_service()
        router = self.container.build_api_router()

        self.assertIsInstance(router, ApiRouter)
        self.assertIs(router._service, service)
        self.assertIs(router, self.container.build_api_router())


class TestApiServiceJsonBoundary(unittest.TestCase):
    def test_scheduler_state_serializes_datetime(self) -> None:
        scheduler = Mock(spec=SchedulerService)
        scheduler.state.return_value = SchedulerState(
            running=True,
            active_jobs=1,
            last_tick=datetime(2026, 8, 10, 12, 30, tzinfo=timezone.utc),
        )
        service = ApiService(scheduler=scheduler)

        response = service.scheduler_state()

        self.assertEqual(response.payload["running"], True)
        self.assertEqual(response.payload["active_jobs"], 1)
        self.assertEqual(response.payload["last_tick"], "2026-08-10T12:30:00+00:00")

    def test_registered_jobs_excludes_callbacks(self) -> None:
        scheduler = Mock(spec=SchedulerService)
        scheduler.registered_jobs.return_value = (
            RegisteredJob(
                definition=ScheduledJob(
                    job_id="scan",
                    job_name="Market Scan",
                    interval_seconds=60,
                    enabled=True,
                    metadata={"symbols": ["BTCUSDT"]},
                ),
                callback=lambda: None,
            ),
        )
        service = ApiService(scheduler=scheduler)

        response = service.registered_jobs()

        job = response.payload["jobs"][0]
        self.assertEqual(job["job_id"], "scan")
        self.assertEqual(job["interval_seconds"], 60)
        self.assertNotIn("callback", job)
        self.assertEqual(response.payload["count"], 1)


if __name__ == "__main__":
    unittest.main()
