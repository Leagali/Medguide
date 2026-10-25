"""Recupera jobs reais, sem iniciar a descoberta antes do clique na interface."""

from medguide.workers.celery_app import app


def recovery_schedule(schedule: dict) -> dict:
    return {
        name: entry for name, entry in schedule.items() if entry["task"] == "medguide.reconcile"
    }


if __name__ == "__main__":
    app.conf.beat_schedule = recovery_schedule(app.conf.beat_schedule)
    app.Beat(loglevel="INFO", schedule="/tmp/celerybeat-video").run()
