"""Spanish demo project seed. Idempotent: no-ops once any project exists.

Gated by ``settings.seed_on_startup`` at the call site (lifespan).
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import List

from app.db import dumps, one
from core.defaults import DEFAULT_PARAMETERS


def seed_database(conn: sqlite3.Connection) -> None:
    if one(conn, "SELECT id FROM projects LIMIT 1"):
        return
    start = date(2026, 7, 1)
    end = date(2026, 10, 15)
    cur = conn.execute(
        """INSERT INTO projects (name, description, sponsor, project_manager, start_date, end_date, methodology, status, budget, currency, parameters_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "Plataforma Cliente 360",
            "Implementación de una solución empresarial con control PMP y ejecución Scrum.",
            "Comité de Dirección",
            "Carlos Méndez",
            start.isoformat(),
            end.isoformat(),
            "Híbrida PMP + Scrum",
            "En ejecución",
            125000000,
            "COP",
            dumps(DEFAULT_PARAMETERS),
        ),
    )
    project_id = cur.lastrowid
    people = [
        ("Ana López", "Project Manager", "ana@empresa.com", 80),
        ("Carlos Méndez", "PMO Director", "carlos@empresa.com", 70),
        ("María González", "Líder Técnica", "maria@empresa.com", 100),
        ("Equipo Dev", "Desarrollo", "dev@empresa.com", 100),
        ("QA Team", "Calidad", "qa@empresa.com", 90),
        ("DevOps", "Infraestructura", "devops@empresa.com", 60),
    ]
    conn.executemany("INSERT INTO resources (project_id, name, role, email, capacity) VALUES (?, ?, ?, ?, ?)", [(project_id, *p) for p in people])

    rows = [
        ("Acta de constitución", "Inicio", "task", start, start + timedelta(days=3), 100, "Ana López", "Completada", 0, 4000000),
        ("Identificación de interesados", "Inicio", "task", start + timedelta(days=2), start + timedelta(days=7), 100, "Ana López", "Completada", 0, 3000000),
        ("Alcance preliminar", "Inicio", "task", start + timedelta(days=6), start + timedelta(days=10), 100, "Ana López", "Completada", 0, 2500000),
        ("Plan de gestión del proyecto", "Planeación", "task", start + timedelta(days=8), start + timedelta(days=18), 100, "Carlos Méndez", "Completada", 0, 6500000),
        ("Plan de alcance", "Planeación", "task", start + timedelta(days=14), start + timedelta(days=24), 85, "Carlos Méndez", "En progreso", 0, 5000000),
        ("Plan de tiempo / cronograma", "Planeación", "task", start + timedelta(days=20), start + timedelta(days=33), 80, "María González", "En progreso", 0, 7000000),
        ("Plan de costos", "Planeación", "task", start + timedelta(days=25), start + timedelta(days=37), 60, "Jorge Ramírez", "En progreso", 0, 4500000),
        ("Aprobación del plan", "Planeación", "milestone", start + timedelta(days=39), start + timedelta(days=39), 0, "Comité de Dirección", "Pendiente", 0, 0),
        ("Sprint 1 - Configuración inicial", "Ejecución", "task", start + timedelta(days=42), start + timedelta(days=55), 100, "Equipo Dev", "Completada", 21, 14500000),
        ("Sprint 2 - Módulo de Clientes", "Ejecución", "task", start + timedelta(days=56), start + timedelta(days=69), 65, "Equipo Dev", "En progreso", 34, 16000000),
        ("Sprint 3 - Integraciones", "Ejecución", "task", start + timedelta(days=70), start + timedelta(days=83), 20, "Equipo Dev", "En progreso", 34, 17000000),
        ("Sprint 4 - Reportes", "Ejecución", "task", start + timedelta(days=84), start + timedelta(days=97), 0, "Equipo Dev", "Pendiente", 28, 12000000),
        ("Pruebas funcionales", "Pruebas", "task", start + timedelta(days=88), start + timedelta(days=101), 30, "QA Team", "En progreso", 0, 9000000),
        ("Pruebas de integración", "Pruebas", "task", start + timedelta(days=98), start + timedelta(days=107), 10, "QA Team", "Pendiente", 0, 7000000),
        ("Pruebas de aceptación UAT", "Pruebas", "milestone", start + timedelta(days=108), start + timedelta(days=108), 0, "Usuarios Clave", "Pendiente", 0, 0),
        ("Despliegue a producción", "Cierre", "task", start + timedelta(days=110), start + timedelta(days=114), 0, "DevOps", "Pendiente", 0, 8000000),
        ("Cierre administrativo", "Cierre", "task", start + timedelta(days=115), start + timedelta(days=120), 0, "Carlos Méndez", "Pendiente", 0, 3000000),
        ("Lecciones aprendidas", "Cierre", "milestone", start + timedelta(days=121), start + timedelta(days=121), 0, "Carlos Méndez", "Pendiente", 0, 0),
    ]
    task_ids: List[int] = []
    for idx, row in enumerate(rows, start=1):
        cur = conn.execute(
            """INSERT INTO tasks (project_id, title, phase, task_type, start_date, end_date, progress, owner, status, story_points, budget, order_index)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (project_id, row[0], row[1], row[2], row[3].isoformat(), row[4].isoformat(), row[5], row[6], row[7], row[8], row[9], idx),
        )
        task_ids.append(cur.lastrowid)
    dep_pairs = [(3, 4), (6, 8), (8, 9), (9, 10), (10, 11), (11, 12), (12, 13), (13, 14), (14, 15), (15, 16), (16, 17), (17, 18)]
    conn.executemany("INSERT INTO dependencies (project_id, predecessor_id, successor_id, dependency_type) VALUES (?, ?, ?, 'FS')", [(project_id, task_ids[a - 1], task_ids[b - 1]) for a, b in dep_pairs])

    sprints = [
        ("Sprint 1 - Configuración inicial", "Preparar arquitectura base y pipeline", start + timedelta(days=42), start + timedelta(days=55), "Cerrado", 28),
        ("Sprint 2 - Módulo de Clientes", "Entregar gestión base de clientes", start + timedelta(days=56), start + timedelta(days=69), "En curso", 34),
        ("Sprint 3 - Integraciones", "Conectar APIs y servicios externos", start + timedelta(days=70), start + timedelta(days=83), "Planeado", 34),
    ]
    sprint_ids: List[int] = []
    for s in sprints:
        cur = conn.execute("INSERT INTO sprints (project_id, name, goal, start_date, end_date, status, velocity) VALUES (?, ?, ?, ?, ?, ?, ?)", (project_id, s[0], s[1], s[2].isoformat(), s[3].isoformat(), s[4], s[5]))
        sprint_ids.append(cur.lastrowid)
    stories = [
        (sprint_ids[1], "US-21 Listado de clientes", "En progreso", 5, "María González", "Alta"),
        (sprint_ids[1], "US-22 Ficha de cliente", "En progreso", 8, "Equipo Dev", "Alta"),
        (sprint_ids[1], "US-23 Búsqueda avanzada", "En progreso", 5, "Equipo Dev", "Media"),
        (sprint_ids[1], "US-24 Validar datos de cliente", "Por hacer", 5, "QA Team", "Media"),
        (sprint_ids[1], "US-25 Carga masiva de clientes", "Por hacer", 8, "Equipo Dev", "Alta"),
        (sprint_ids[1], "US-26 Exportar reportes", "Por hacer", 5, "Equipo Dev", "Media"),
        (sprint_ids[0], "US-17 Configuración inicial", "Hecho", 3, "DevOps", "Alta"),
        (sprint_ids[0], "US-18 Modelos de datos", "Hecho", 8, "María González", "Alta"),
        (sprint_ids[0], "US-19 Servicios API", "Hecho", 8, "Equipo Dev", "Alta"),
    ]
    conn.executemany("INSERT INTO stories (project_id, sprint_id, title, status, points, assignee, priority) VALUES (?, ?, ?, ?, ?, ?, ?)", [(project_id, *s) for s in stories])
    risks = [
        ("Retraso por dependencias de integración", 4, 4, "Asegurar APIs tempranas y ambiente de pruebas", "Abierto", "María González"),
        ("Capacidad limitada de QA", 3, 4, "Priorizar pruebas críticas y automatizar regresión", "Abierto", "QA Team"),
        ("Cambios de alcance no controlados", 3, 3, "Activar comité de cambios y backlog grooming", "Abierto", "Carlos Méndez"),
        ("Aprobación tardía del sponsor", 2, 4, "Agendar stage gates desde la planeación", "Mitigado", "Ana López"),
    ]
    conn.executemany(
        "INSERT INTO risks (project_id, title, probability, impact, response, status, owner) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(project_id, title, prob, impact, response, status, owner) for title, prob, impact, response, status, owner in risks],
    )
    conn.commit()
