"""
Locust Performance Tests for Plot Palette API

Tests API Gateway endpoints under load to measure:
- Throughput (requests/second)
- Response times (p50, p95, p99)
- Error rates
- Concurrent user capacity

Usage:
    locust -f tests/performance/locustfile.py --host=$API_ENDPOINT

    # With UI
    locust -f tests/performance/locustfile.py --host=$API_ENDPOINT --web-host=0.0.0.0

    # Headless mode
    locust -f tests/performance/locustfile.py --host=$API_ENDPOINT \
        --headless --users=50 --spawn-rate=5 --run-time=5m

NOTE: Phase 8 is code writing only. These tests will run against
deployed infrastructure in Phase 9.
"""

import json
import random
import time
from locust import HttpUser, task, between, events
from locust.exception import RescheduleTask


class PlotPaletteUser(HttpUser):
    """
    Simulated user interacting with Plot Palette API.

    Performs realistic workflows:
    - Authentication
    - Job creation
    - Job monitoring
    - Template management
    - Seed data upload
    """

    # Wait 1-3 seconds between requests (realistic user behavior)
    wait_time = between(1, 3)

    # Shared state
    access_token = None
    job_id = None
    template_id = None

    def on_start(self):
        """Called when user starts - authenticate."""
        self.login()

    def on_stop(self):
        """Called when user stops - cleanup."""
        pass

    def login(self):
        """Authenticate user and get JWT token."""
        # Note: In real test, use Cognito auth endpoint
        # For load testing, might use pre-generated tokens
        response = self.client.post(
            "/auth/login",
            json={
                "username": f"test-user-{random.randint(1, 1000)}@example.com",
                "password": "TestPassword123!"
            },
            name="POST /auth/login",
            catch_response=True
        )

        if response.status_code == 200:
            data = response.json()
            self.access_token = data.get("access_token")
            response.success()
        else:
            response.failure(f"Login failed: {response.status_code}")

    @property
    def headers(self):
        """Get authorization headers."""
        if not self.access_token:
            self.login()
        return {"Authorization": f"Bearer {self.access_token}"}

    @task(10)
    def list_jobs(self):
        """List user's jobs - most common operation."""
        response = self.client.get(
            "/jobs",
            headers=self.headers,
            name="GET /jobs",
            catch_response=True
        )

        if response.status_code == 200:
            jobs = response.json()
            response.success()

            # Save job ID for other operations
            if jobs and len(jobs) > 0:
                self.job_id = jobs[0].get("job_id")
        else:
            response.failure(f"Failed to list jobs: {response.status_code}")

    @task(5)
    def get_job_details(self):
        """Get detailed job information."""
        if not self.job_id:
            # Need to list jobs first
            raise RescheduleTask()

        response = self.client.get(
            f"/jobs/{self.job_id}",
            headers=self.headers,
            name="GET /jobs/{id}",
            catch_response=True
        )

        if response.status_code == 200:
            response.success()
        elif response.status_code == 404:
            # Job not found, reset job_id
            self.job_id = None
            response.success()  # Not a failure, just need different job
        else:
            response.failure(f"Failed to get job: {response.status_code}")

    @task(2)
    def create_job(self):
        """Create new generation job."""
        job_data = {
            "name": f"Load Test Job {random.randint(1, 10000)}",
            "template_id": self.template_id or "sample-template-1",
            "seed_data_path": f"s3://test-bucket/seed/data-{random.randint(1, 100)}.json",
            "target_records": random.choice([100, 500, 1000]),
            "budget_limit": random.choice([5.0, 10.0, 25.0])
        }

        response = self.client.post(
            "/jobs",
            headers=self.headers,
            json=job_data,
            name="POST /jobs",
            catch_response=True
        )

        if response.status_code == 201:
            data = response.json()
            self.job_id = data.get("job_id")
            response.success()
        elif response.status_code == 400:
            response.success()  # Validation error is expected sometimes
        else:
            response.failure(f"Failed to create job: {response.status_code}")

    @task(8)
    def list_templates(self):
        """List available templates."""
        response = self.client.get(
            "/templates",
            headers=self.headers,
            name="GET /templates",
            catch_response=True
        )

        if response.status_code == 200:
            templates = response.json()
            response.success()

            # Save template ID
            if templates and len(templates) > 0:
                self.template_id = templates[0].get("template_id")
        else:
            response.failure(f"Failed to list templates: {response.status_code}")

    @task(3)
    def get_template_details(self):
        """Get template details."""
        if not self.template_id:
            raise RescheduleTask()

        response = self.client.get(
            f"/templates/{self.template_id}",
            headers=self.headers,
            name="GET /templates/{id}",
            catch_response=True
        )

        if response.status_code == 200:
            response.success()
        elif response.status_code == 404:
            self.template_id = None
            response.success()
        else:
            response.failure(f"Failed to get template: {response.status_code}")

    @task(1)
    def create_template(self):
        """Create new template."""
        template_data = {
            "name": f"Load Test Template {random.randint(1, 10000)}",
            "description": "Template created by load test",
            "steps": [
                {
                    "id": "step1",
                    "model": "meta.llama3-1-8b-instruct-v1:0",
                    "prompt": "Generate text about {{ topic }}"
                }
            ],
            "is_public": False
        }

        response = self.client.post(
            "/templates",
            headers=self.headers,
            json=template_data,
            name="POST /templates",
            catch_response=True
        )

        if response.status_code == 201:
            data = response.json()
            self.template_id = data.get("template_id")
            response.success()
        else:
            response.failure(f"Failed to create template: {response.status_code}")

    @task(1)
    def get_dashboard_stats(self):
        """Get dashboard statistics."""
        if not self.job_id:
            raise RescheduleTask()

        response = self.client.get(
            f"/dashboard/{self.job_id}",
            headers=self.headers,
            name="GET /dashboard/{job_id}",
            catch_response=True
        )

        if response.status_code == 200:
            response.success()
        elif response.status_code == 404:
            self.job_id = None
            response.success()
        else:
            response.failure(f"Failed to get dashboard: {response.status_code}")

    @task(1)
    def delete_job(self):
        """Delete completed job."""
        if not self.job_id:
            raise RescheduleTask()

        response = self.client.delete(
            f"/jobs/{self.job_id}",
            headers=self.headers,
            name="DELETE /jobs/{id}",
            catch_response=True
        )

        if response.status_code in [200, 204]:
            self.job_id = None
            response.success()
        elif response.status_code == 404:
            self.job_id = None
            response.success()
        else:
            response.failure(f"Failed to delete job: {response.status_code}")


class AdminUser(HttpUser):
    """
    Admin user with elevated permissions.

    Tests admin-only endpoints under load.
    """

    wait_time = between(2, 5)
    weight = 1  # Only 1 admin for every 10 regular users

    access_token = None

    def on_start(self):
        """Login as admin."""
        self.login()

    def login(self):
        """Authenticate as admin."""
        response = self.client.post(
            "/auth/login",
            json={
                "username": "admin@example.com",
                "password": "AdminPassword123!"
            },
            name="POST /auth/login (admin)",
            catch_response=True
        )

        if response.status_code == 200:
            data = response.json()
            self.access_token = data.get("access_token")
            response.success()
        else:
            response.failure(f"Admin login failed: {response.status_code}")

    @property
    def headers(self):
        """Get admin authorization headers."""
        if not self.access_token:
            self.login()
        return {"Authorization": f"Bearer {self.access_token}"}

    @task(5)
    def list_all_jobs(self):
        """List all jobs (admin only)."""
        response = self.client.get(
            "/admin/jobs",
            headers=self.headers,
            name="GET /admin/jobs",
            catch_response=True
        )

        if response.status_code == 200:
            response.success()
        else:
            response.failure(f"Failed to list all jobs: {response.status_code}")

    @task(2)
    def get_system_stats(self):
        """Get system-wide statistics."""
        response = self.client.get(
            "/admin/stats",
            headers=self.headers,
            name="GET /admin/stats",
            catch_response=True
        )

        if response.status_code == 200:
            response.success()
        else:
            response.failure(f"Failed to get system stats: {response.status_code}")


# Custom test scenarios

class SpikeLoadUser(HttpUser):
    """
    User that generates spike load.

    Tests system behavior under sudden traffic bursts.
    """

    wait_time = between(0.1, 0.5)  # Very short wait time
    weight = 0  # Only spawn when explicitly requested

    @task
    def rapid_job_listing(self):
        """Rapidly list jobs to simulate spike."""
        # Would need auth token
        self.client.get("/jobs", headers={"Authorization": "Bearer test-token"})


# Event listeners for custom metrics

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts."""
    print("Load test starting...")
    print(f"Target host: {environment.host}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops."""
    print("\nLoad test completed!")
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Total failures: {environment.stats.total.num_failures}")
    print(f"Average response time: {environment.stats.total.avg_response_time:.2f}ms")
    print(f"Median response time: {environment.stats.total.median_response_time:.2f}ms")
    print(f"95th percentile: {environment.stats.total.get_response_time_percentile(0.95):.2f}ms")
    print(f"99th percentile: {environment.stats.total.get_response_time_percentile(0.99):.2f}ms")


if __name__ == "__main__":
    import os
    os.system("locust -f locustfile.py")
