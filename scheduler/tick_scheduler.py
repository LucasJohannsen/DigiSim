import asyncio
import datetime
import json
import time
from pathlib import Path
from typing import List

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from models.sim_context import SimContext
from scheduler.calendar_driven_runner import CalendarDrivenRunner
from utils.state_manager import StateManager
from utils.logger import get_logger

logger = get_logger("tick_scheduler")


class TickScheduler:
    def __init__(
        self,
        contexts: List[SimContext],
        tick_time: str = "06:00",
        state_dir: str = "./state",
        event_dispatcher=None,
        max_concurrent_fields: int = 10
    ) -> None:
        self.contexts = contexts
        self.tick_time = tick_time
        self.state_dir = state_dir
        self.state_manager = StateManager(state_dir)
        self.event_dispatcher = event_dispatcher
        self.max_concurrent_fields = max_concurrent_fields
        
        self.tick_hour, self.tick_minute = self._parse_tick_time(tick_time)
        
        self.runners = {}
        for context in contexts:
            runner = CalendarDrivenRunner(context)
            snapshot = self.state_manager.load(context.field_id)
            if snapshot:
                runner.apply_state_snapshot(snapshot)
                logger.info("State restored", field_id=context.field_id, last_tick_date=str(snapshot.last_tick_date))
            self.runners[context.field_id] = runner
        
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(
            self._daily_tick_sync,
            CronTrigger(hour=self.tick_hour, minute=self.tick_minute),
            id='daily_tick'
        )
        
        self._running = False
    
    def _parse_tick_time(self, tick_time: str) -> tuple[int, int]:
        parts = tick_time.split(":")
        hour = int(parts[0])
        minute = int(parts[1])
        return hour, minute
    
    def _daily_tick_sync(self) -> None:
        asyncio.run(self.daily_tick())
    
    async def daily_tick(self) -> None:
        today = datetime.date.today()
        
        semaphore = asyncio.Semaphore(self.max_concurrent_fields)
        
        async def process_field(field_id: int, runner: CalendarDrivenRunner):
            async with semaphore:
                try:
                    events = await asyncio.to_thread(runner.tick, today)
                    
                    if self.event_dispatcher:
                        for event in events:
                            await asyncio.to_thread(
                                self.event_dispatcher.send_event,
                                event,
                                runner.context
                            )
                    
                    await asyncio.to_thread(self.state_manager.save, runner, today)
                    logger.info("Tick completed", field_id=field_id, events_sent=len(events), tick_date=str(today))
                    return {"field_id": field_id, "success": True, "events": len(events)}
                except Exception as e:
                    logger.error("Tick failed", field_id=field_id, error=str(e))
                    return {"field_id": field_id, "success": False, "error": str(e)}
        
        tasks = [process_field(fid, runner) for fid, runner in self.runners.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        total = len(results)
        logger.info("Tick summary", successful=successful, total=total, tick_date=str(today))
        
        heartbeat = {
            "last_tick": datetime.datetime.now().isoformat(),
            "successful_fields": successful,
            "total_fields": total,
        }
        heartbeat_path = Path(self.state_dir) / "heartbeat.json"
        heartbeat_path.write_text(json.dumps(heartbeat))
        logger.info("Heartbeat written", path=str(heartbeat_path), successful=successful, total=total)
    
    def start(self) -> None:
        self.scheduler.start()
        self._running = True
        logger.info("TickScheduler started", field_count=len(self.runners), tick_time=self.tick_time, max_concurrent=self.max_concurrent_fields)
        
        try:
            while self._running:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            self.stop()
    
    def stop(self) -> None:
        self._running = False
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        logger.info("TickScheduler stopped")
