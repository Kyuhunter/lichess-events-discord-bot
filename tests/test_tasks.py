import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

import src.tasks as tasks_mod

@pytest.fixture
def dummy_scheduler(monkeypatch):
    created = {}
    # Dummy scheduler to capture jobs and start called
    class DummyScheduler:
        def __init__(self):
            created['inst'] = self
            self.jobs = []
            self.started = False
        def add_job(self, func, trigger):
            self.jobs.append(func)
        def start(self):
            self.started = True
    monkeypatch.setattr(tasks_mod, 'AsyncIOScheduler', DummyScheduler)
    # Stub CronTrigger.from_crontab
    monkeypatch.setattr(tasks_mod.CronTrigger, 'from_crontab', lambda expr: 'dummy')
    return created

@pytest.mark.asyncio
async def test_start_background_tasks(monkeypatch, dummy_scheduler):
    # Stub sync_events_for_guild to record calls
    call_log = []
    async def fake_sync(guild, SETTINGS, bot, verbose=False, prefetched_events=None):
        call_log.append((guild.id, SETTINGS.get(str(guild.id), None)))
    monkeypatch.setattr(tasks_mod, 'sync_events_for_guild', fake_sync)

    # Create bot with two dummy guilds
    guild1 = MagicMock(id=1)
    guild2 = MagicMock(id=2)
    bot = MagicMock(guilds=[guild1, guild2])
    # SETTINGS: guild2 auto_sync disabled
    SETTINGS = {'1': {}, '2': {'auto_sync': False}}

    # Run task setup
    tasks_mod.start_background_tasks(bot, SETTINGS)

    # Scheduler should have started and one job added
    scheduler = dummy_scheduler['inst']
    assert scheduler.started is True
    assert len(scheduler.jobs) == 1

    # Execute the scheduled job coroutine
    sync_job = scheduler.jobs[0]
    await sync_job()

    # Only guild1 should have been synced (default_auto True)
    assert call_log == [(1, {})]

@pytest.mark.asyncio
async def test_start_background_tasks_with_config_error(monkeypatch, tmp_path, caplog):
    # Force config.yaml load to throw
    monkeypatch.setattr('builtins.open', lambda *args, **kwargs: (_ for _ in ()).throw(Exception("fail open")))
    # Create a dummy scheduler class
    class DummyScheduler:
        def __init__(self):
            self.jobs = []
            self.started = False
        def add_job(self, func, trigger):
            self.jobs.append(func)
        def start(self):
            self.started = True
    # Patch AsyncIOScheduler and CronTrigger.from_crontab
    monkeypatch.setattr(tasks_mod, 'AsyncIOScheduler', DummyScheduler)
    monkeypatch.setattr(tasks_mod.CronTrigger, 'from_crontab', lambda expr: 'dummy')
    caplog.set_level('ERROR')
    # Run with broken config
    tasks_mod.start_background_tasks(MagicMock(guilds=[]), {})
    # Should log error about loading scheduler config
    assert any("Failed to load scheduler config" in rec.message for rec in caplog.records)

@pytest.mark.asyncio
async def test_sync_job_exception(monkeypatch, caplog, dummy_scheduler):
    # Patch sync to raise an exception
    monkeypatch.setattr(tasks_mod, 'sync_events_for_guild', AsyncMock(side_effect=Exception('sync fail')))
    # Prepare bot with one guild
    guild = MagicMock(id=10)
    bot = MagicMock(guilds=[guild])
    SETTINGS = {'10': {}}
    caplog.set_level('ERROR')
    # Start tasks
    tasks_mod.start_background_tasks(bot, SETTINGS)
    scheduler = dummy_scheduler['inst']
    sync_job = scheduler.jobs[0]
    # Run job and capture error log
    await sync_job()
    assert any('Error syncing tournaments for guild 10' in rec.message for rec in caplog.records)
