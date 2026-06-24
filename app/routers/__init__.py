"""Aggregates every domain router into a single list for app.main."""
from app.routers import (
    ai,
    bootstrap,
    dependencies,
    health,
    projects,
    resources,
    risks,
    sprints,
    stories,
    tasks,
)

all_routers = [
    health.router,
    bootstrap.router,
    projects.router,
    tasks.router,
    dependencies.router,
    sprints.router,
    stories.router,
    risks.router,
    resources.router,
    ai.router,
]
