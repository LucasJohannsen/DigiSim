import datetime
import time
from typing import List

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from models.sim_context import SimContext
from scheduler.calendar_driven_runner import CalendarDrivenRunner
from utils.state_manager import StateManager


class TickScheduler:
    def __init__(self, contexts: List[SimContext], tick_time: str = "06:00", state_dir: str = "./state", event_dispatcher=None) -> None:
        self.contexts = contexts
        self.tick_time = tick_time
        self.state_manager = StateManager(state_dir)
        self.event_dispatcher = event_dispatcher
        
        self.tick_hour, self.tick_minute = self._parse_tick_time(tick_time)
        
        self.runners = {}
        for context in contexts:
            runner = CalendarDrivenRunner(context)
            snapshot = self.state_manager.load(context.field_id)
            if snapshot:
                runner.apply_state_snapshot(snapshot)
                print(f"[INFO] Field {context.field_id}: state restored (last tick: {snapshot.last_tick_date})")
            self.runners[context.field_id] = runner
        
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
                if self.event_dispatcher:
                    for event in events:
                        self.event_dispatcher.send_event(event, runner.context)
                self.state_manager.save(runner, today)
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
