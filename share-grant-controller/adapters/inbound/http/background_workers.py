import asyncio
import logging
from application.ports.inbound.publish_outbox_port import PublishOutboxPort
from application.ports.inbound.reconcile_dispatches_port import ReconcileDispatchesPort
from infrastructure.config import Settings, settings

logger = logging.getLogger(__name__)


class BackgroundWorkers:
    def __init__(
        self,
        publish_outbox_port: PublishOutboxPort,
        reconcile_dispatches_port: ReconcileDispatchesPort,
        config: Settings = settings,
    ):
        self.publish_outbox_port = publish_outbox_port
        self.reconcile_dispatches_port = reconcile_dispatches_port
        self.config = config
        self._running = False
        self._tasks = []

    async def _run_outbox_loop(self) -> None:
        logger.info(
            f"Starting Outbox Publisher worker (interval: {self.config.outbox_publisher_interval_seconds}s)"
        )
        while self._running:
            try:
                await asyncio.to_thread(self.publish_outbox_port.publish_pending)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Outbox Publisher loop: {e}")

            try:
                await asyncio.sleep(self.config.outbox_publisher_interval_seconds)
            except asyncio.CancelledError:
                break

    async def _run_reconciler_loop(self) -> None:
        logger.info(
            f"Starting Reconciler worker (interval: {self.config.reconciler_interval_seconds}s)"
        )
        while self._running:
            try:
                await asyncio.to_thread(self.reconcile_dispatches_port.reconcile)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Reconciler loop: {e}")

            try:
                await asyncio.sleep(self.config.reconciler_interval_seconds)
            except asyncio.CancelledError:
                break

    def start(self) -> None:
        self._running = True
        self._tasks.append(asyncio.create_task(self._run_outbox_loop()))
        self._tasks.append(asyncio.create_task(self._run_reconciler_loop()))

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
