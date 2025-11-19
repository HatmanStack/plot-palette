"""
Plot Palette - ECS Generation Worker

This worker pulls jobs from the DynamoDB queue, generates synthetic data using
AWS Bedrock, and implements checkpoint-based graceful shutdown for Spot interruptions.
"""

import signal
import sys
import logging
import json
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Worker:
    """ECS Fargate worker for data generation."""

    def __init__(self):
        self.shutdown_requested = False
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        logger.info("Worker initialized")

    def handle_shutdown(self, signum, frame):
        """Handle SIGTERM for Spot interruption (120 seconds to shutdown)."""
        logger.info("Received SIGTERM (Spot interruption), initiating graceful shutdown")
        self.shutdown_requested = True
        # Set alarm to force exit after 100 seconds (leave 20s buffer)
        signal.alarm(100)

    def run(self):
        """Main worker loop - process one job then exit."""
        logger.info("Worker started")
        try:
            job = self.get_next_job()

            if job:
                logger.info(f"Processing job {job['job_id']}")
                self.process_job(job)
            else:
                logger.info("No jobs in queue")

        except Exception as e:
            logger.error(f"Worker error: {str(e)}", exc_info=True)
            sys.exit(1)

        finally:
            logger.info("Worker shutdown complete")
            sys.exit(0)

    def get_next_job(self):
        """Pull next job from queue - implementation in next task."""
        # This will be implemented in Task 3
        logger.info("get_next_job called (stub)")
        return None

    def process_job(self, job):
        """Process a single job - implementation in next tasks."""
        # This will be implemented across Tasks 3-7
        logger.info(f"process_job called for {job['job_id']} (stub)")
        pass


if __name__ == "__main__":
    worker = Worker()
    worker.run()
