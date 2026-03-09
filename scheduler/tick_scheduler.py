import datetime
import time
from typing import List

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from models.sim_context import SimContext
from scheduler.calendar_driven_runner import CalendarDrivenRunner


class TickScheduler:
    def __init__(self, contexts: List[SimContext], tick_time: str = "06:00") -> None:
        self.contexts = contexts
        self.tick_time = tick_time
        
        self.tick_hour, self.tick_minute = self._parse_tick_time(tick_time)
        
        self.runners = {}
        for context in contexts:
            self.runners[context.field_id] = CalendarDrivenRunner(context)
        
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(
            self.daily_tick,
            CronTrigger(hour=self.tick_hour, minute=self.tick_minute),
            id='daily_tick'
        )
        
        self._running = False
    
    def _parse_tick_time(self, tick_time: str) -> tuple[int, int]:
        parts = tick_time.split(":")
        hour = int(parts[0])
        minute = int(parts[1])
        return hour, minute
    
    def daily_tick(self) -> None:
        today = datetime.date.today()
        for field_id, runner in self.runners.items():
            try:
                events = runner.tick(today)
                print(f"[INFO] Field {field_id}: {len(events)} events on {today}")
            except Exception as e:
                print(f"[ERROR] Field {field_id} tick failed: {e}")
    
    def start(self) -> None:
        self.scheduler.start()
        self._running = True
        
        try:
            while self._running:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            self.stop()
    
    def stop(self) -> None:
        self._running = False
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
