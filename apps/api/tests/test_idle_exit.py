from app.core.idle_exit import IdleExit, STRIKES


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


def make(enabled=True):
    clock, exited = Clock(), []
    return IdleExit(enabled, idle_seconds=180, exit=exited.append, clock=clock), clock, exited


def run_checks(idle, count):
    for _ in range(count):
        idle.check()


def test_never_exits_before_the_first_ping():
    idle, clock, exited = make()
    clock.now = 10_000
    run_checks(idle, 10)
    assert exited == []


def test_exits_after_the_pings_stop_for_three_minutes():
    idle, clock, exited = make()
    idle.beat()
    clock.now = 179
    run_checks(idle, 10)
    assert exited == []
    clock.now = 181
    run_checks(idle, STRIKES - 1)
    assert exited == []  # one more look, in case the PC just woke up
    idle.check()
    assert exited == [0]


def test_a_ping_in_between_resets_the_count():
    idle, clock, exited = make()
    idle.beat()
    clock.now = 200
    run_checks(idle, STRIKES - 1)
    idle.beat()
    run_checks(idle, 5)
    assert exited == []


def test_work_in_progress_keeps_it_alive_and_restarts_the_countdown_when_done():
    idle, clock, exited = make()
    idle.beat()
    idle.begin()  # a render is running
    clock.now = 1_000
    run_checks(idle, 10)
    assert exited == []
    idle.end()  # finished at t=1000: the window has been closed for a long time, but the countdown starts now
    run_checks(idle, 10)
    assert exited == []
    clock.now = 1_200
    run_checks(idle, STRIKES)
    assert exited == [0]


def test_heartbeat_endpoint_answers(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app

    assert TestClient(create_app(repo_root=tmp_path)).get("/api/heartbeat").json() == {"ok": True}
