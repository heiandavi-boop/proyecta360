from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional

from proyecta360.core.config import DEFAULT_PARAMETERS
from proyecta360.core.database import all_rows, deep_merge, dumps, loads, one
from proyecta360.core.defaults import PROYECTA360_LAC_STRATEGIC_FRAMEWORK

HistoryFn = Callable[[sqlite3.Connection, int, str, str, str, str, str], None]
RiskLevelFn = Callable[[int, int, Optional[Dict[str, Any]]], str]


def ensure_proyecta360_lac_strategic_framework(conn: sqlite3.Connection) -> None:
    rows = all_rows(conn, "SELECT id, parameters_json FROM projects WHERE name IN (?, ?)", ("Proyecta360 LAC", "Proyecta360LAC"))
    for row in rows:
        params = loads(row.get("parameters_json"), DEFAULT_PARAMETERS) or {}
        existing = params.get("strategic_framework") or {}
        merged = {
            key: (existing.get(key) if str(existing.get(key) or "").strip() else value)
            for key, value in PROYECTA360_LAC_STRATEGIC_FRAMEWORK.items()
        }
        if existing == merged:
            continue
        params["strategic_framework"] = merged
        conn.execute("UPDATE projects SET parameters_json = ? WHERE id = ?", (dumps(deep_merge(DEFAULT_PARAMETERS, params)), row["id"]))


def ensure_mvp_data(conn: sqlite3.Connection, add_history: HistoryFn) -> None:
    projects = all_rows(conn, "SELECT * FROM projects ORDER BY id")
    for project in projects:
        project_id = project["id"]
        if project["name"] == "Plataforma Cliente 360":
            conn.execute(
                """UPDATE projects
                   SET name = ?, description = ?, sponsor = ?, project_manager = ?, methodology = ?
                   WHERE id = ?""",
                (
                    "Proyecta360 LAC",
                    "Plataforma para la gesti\u00f3n integral de proyectos financiados y productos de conocimiento en investigaci\u00f3n, innovaci\u00f3n y cooperaci\u00f3n internacional.",
                    "Universidad / Cooperante LAC",
                    "Alejandra Trujillo",
                    "H\u00edbrida por componentes",
                    project_id,
                ),
            )
            project = one(conn, "SELECT * FROM projects WHERE id = ?", (project_id,)) or project
        if not one(conn, "SELECT id FROM components WHERE project_id = ? LIMIT 1", (project_id,)):
            defaults = [
                ("Componente cientifico", "Tradicional", project["project_manager"] or "Responsable cientifico", "Gestionar hitos y resultados cientificos", 0),
                ("Componente tecnologico", "Scrum", "Equipo tecnologico", "Construir y validar la plataforma web", 0),
                ("Componente administrativo", "Tradicional", project["sponsor"] or "Administrador de fondos", "Gestionar fondos, soportes y financiador", 0),
                ("Componente divulgacion", "Kanban", "Equipo divulgacion", "Publicar productos de conocimiento", 0),
            ]
            component_ids = []
            for item in defaults:
                cur = conn.execute(
                    "INSERT INTO components (project_id, name, methodology, owner, objective, progress) VALUES (?, ?, ?, ?, ?, ?)",
                    (project_id, *item),
                )
                component_ids.append(cur.lastrowid)
            phases = {"Inicio": component_ids[2], "Planeacion": component_ids[2], "Planeación": component_ids[2], "Ejecucion": component_ids[1], "Ejecución": component_ids[1], "Pruebas": component_ids[1], "Cierre": component_ids[3]}
            for task in all_rows(conn, "SELECT id, phase FROM tasks WHERE project_id = ?", (project_id,)):
                conn.execute("UPDATE tasks SET component_id = ? WHERE id = ? AND component_id IS NULL", (phases.get(task["phase"], component_ids[0]), task["id"]))
            add_history(conn, project_id, "Proyecto", project["name"], "Actualizado", "Backfill MVP: componentes por metodologia y fuente unica de informacion.", "Sistema")
        if not one(conn, "SELECT id FROM deliverables WHERE project_id = ? LIMIT 1", (project_id,)):
            components = all_rows(conn, "SELECT * FROM components WHERE project_id = ? ORDER BY id", (project_id,))
            component_lookup = {c["name"]: c["id"] for c in components}
            base = date.fromisoformat(project["start_date"])
            deliverables = [
                (component_lookup.get("Componente cientifico"), "Protocolo o resultado cientifico", "Producto de conocimiento", "Planeado", base + timedelta(days=35)),
                (component_lookup.get("Componente tecnologico"), "MVP web operativo", "Entregable", "Planeado", base + timedelta(days=70)),
                (component_lookup.get("Componente administrativo"), "Soporte de presupuesto y fondos", "Evidencia", "Planeado", base + timedelta(days=45)),
                (component_lookup.get("Componente divulgacion"), "Informe ejecutivo mensual", "Informe", "Planeado", base + timedelta(days=60)),
            ]
            conn.executemany(
                """INSERT INTO deliverables (project_id, component_id, name, deliverable_type, status, due_date, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [(project_id, cid, name, dtype, status, due.isoformat(), "Registro inicial alineado al MVP.") for cid, name, dtype, status, due in deliverables],
            )
        if not one(conn, "SELECT id FROM conversation_threads WHERE project_id = ? LIMIT 1", (project_id,)):
            first_component = one(conn, "SELECT id, name FROM components WHERE project_id = ? ORDER BY id LIMIT 1", (project_id,))
            first_risk = one(conn, "SELECT id, title FROM risks WHERE project_id = ? ORDER BY probability * impact DESC, id LIMIT 1", (project_id,))
            first_deliverable = one(conn, "SELECT id, name FROM deliverables WHERE project_id = ? ORDER BY due_date, id LIMIT 1", (project_id,))
            thread_specs = [
                ("Seguimiento general del proyecto", "Proyecto", None, "Seguimiento", "Aqui se centralizan acuerdos, bloqueos y decisiones para evitar conversaciones dispersas."),
            ]
            if first_component:
                thread_specs.append((f"Coordinacion: {first_component['name']}", "Componente", first_component["id"], "Acuerdo", "Alinear metodologia, responsables y avances del componente."))
            if first_risk:
                thread_specs.append((f"Plan de contingencia: {first_risk['title']}", "Riesgo", first_risk["id"], "Bloqueo", "Registrar decisiones y acciones frente al riesgo principal."))
            if first_deliverable:
                thread_specs.append((f"Evidencia: {first_deliverable['name']}", "Entregable", first_deliverable["id"], "Seguimiento", "Conservar enlaces, soportes y comentarios del producto."))
            for title, context_type, context_id, category, message in thread_specs:
                cur = conn.execute(
                    """INSERT INTO conversation_threads (project_id, title, context_type, context_id, category, created_by)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (project_id, title, context_type, context_id, category, "Sistema"),
                )
                conn.execute(
                    """INSERT INTO conversation_messages (thread_id, project_id, author, message, message_type)
                       VALUES (?, ?, ?, ?, ?)""",
                    (cur.lastrowid, project_id, "Sistema", message, "Comentario"),
                )
    conn.commit()


def seed_database(conn: sqlite3.Connection, add_history: HistoryFn, risk_level: RiskLevelFn) -> None:
    if one(conn, "SELECT id FROM projects LIMIT 1"):
        return
    start = date(2026, 7, 1)
    end = date(2026, 10, 15)
    project_parameters = deep_merge(DEFAULT_PARAMETERS, {"strategic_framework": PROYECTA360_LAC_STRATEGIC_FRAMEWORK})
    cur = conn.execute(
        """INSERT INTO projects (name, description, sponsor, project_manager, start_date, end_date, methodology, status, budget, currency, parameters_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "Proyecta360 LAC",
            "Plataforma para la gesti\u00f3n integral de proyectos financiados y productos de conocimiento en investigaci\u00f3n, innovaci\u00f3n y cooperaci\u00f3n internacional.",
            "Universidad / Cooperante LAC",
            "Alejandra Trujillo",
            start.isoformat(),
            end.isoformat(),
            "H\u00edbrida por componentes",
            "En ejecucion",
            125000000,
            "COP",
            dumps(project_parameters),
        ),
    )
    project_id = cur.lastrowid
    people = [
        ("Alejandra Trujillo", "Gestora del proyecto", "alejandra@proyecta360.ai", 80),
        ("Investigador principal", "Componente cientifico", "investigacion@proyecta360.ai", 75),
        ("Equipo tecnologico", "Scrum / desarrollo", "tech@proyecta360.ai", 90),
        ("Administrador de fondos", "Finanzas y cooperacion", "fondos@proyecta360.ai", 70),
        ("Equipo divulgacion", "Productos de conocimiento", "divulgacion@proyecta360.ai", 85),
        ("PMO regional", "Gobierno y seguimiento", "pmo@proyecta360.ai", 60),
    ]
    conn.executemany("INSERT INTO resources (project_id, name, role, email, capacity) VALUES (?, ?, ?, ?, ?)", [(project_id, *p) for p in people])

    components = [
        ("Componente cientifico", "Tradicional", "Investigador principal", "Gestionar protocolo, hitos de investigacion y resultados cientificos", 55),
        ("Componente tecnologico", "Scrum", "Equipo tecnologico", "Construir la plataforma web asistida por IA", 48),
        ("Componente administrativo", "Tradicional", "Administrador de fondos", "Administrar presupuesto, financiador y soportes", 42),
        ("Componente divulgacion", "Kanban", "Equipo divulgacion", "Publicar entregables y productos de conocimiento", 35),
    ]
    component_ids: List[int] = []
    for c in components:
        cur = conn.execute(
            "INSERT INTO components (project_id, name, methodology, owner, objective, progress) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, *c),
        )
        component_ids.append(cur.lastrowid)

    rows = [
        ("Acta de constitucion", "Inicio", "task", start, start + timedelta(days=3), 100, "Ana Lopez", "Completada", 0, 4000000),
        ("Identificacion de interesados", "Inicio", "task", start + timedelta(days=2), start + timedelta(days=7), 100, "Ana Lopez", "Completada", 0, 3000000),
        ("Alcance preliminar", "Inicio", "task", start + timedelta(days=6), start + timedelta(days=10), 100, "Ana Lopez", "Completada", 0, 2500000),
        ("Plan de gestion del proyecto", "Planeacion", "task", start + timedelta(days=8), start + timedelta(days=18), 100, "Carlos Mendez", "Completada", 0, 6500000),
        ("Plan de alcance", "Planeacion", "task", start + timedelta(days=14), start + timedelta(days=24), 85, "Carlos Mendez", "En progreso", 0, 5000000),
        ("Plan de tiempo / cronograma", "Planeacion", "task", start + timedelta(days=20), start + timedelta(days=33), 80, "Maria Gonzalez", "En progreso", 0, 7000000),
        ("Plan de costos", "Planeacion", "task", start + timedelta(days=25), start + timedelta(days=37), 60, "Jorge Ramirez", "En progreso", 0, 4500000),
        ("Aprobacion del plan", "Planeacion", "milestone", start + timedelta(days=39), start + timedelta(days=39), 0, "Comite de Direccion", "Pendiente", 0, 0),
        ("Sprint 1 - Configuraci\u00f3n inicial", "Ejecucion", "task", start + timedelta(days=42), start + timedelta(days=55), 100, "Equipo Dev", "Completada", 21, 14500000),
        ("Sprint 2 - Modulo de Clientes", "Ejecucion", "task", start + timedelta(days=56), start + timedelta(days=69), 65, "Equipo Dev", "En progreso", 34, 16000000),
        ("Sprint 3 - Integraciones", "Ejecucion", "task", start + timedelta(days=70), start + timedelta(days=83), 20, "Equipo Dev", "En progreso", 34, 17000000),
        ("Sprint 4 - Reportes", "Ejecucion", "task", start + timedelta(days=84), start + timedelta(days=97), 0, "Equipo Dev", "Pendiente", 28, 12000000),
        ("Pruebas funcionales", "Pruebas", "task", start + timedelta(days=88), start + timedelta(days=101), 30, "QA Team", "En progreso", 0, 9000000),
        ("Pruebas de integracion", "Pruebas", "task", start + timedelta(days=98), start + timedelta(days=107), 10, "QA Team", "Pendiente", 0, 7000000),
        ("Pruebas de aceptacion UAT", "Pruebas", "milestone", start + timedelta(days=108), start + timedelta(days=108), 0, "Usuarios Clave", "Pendiente", 0, 0),
        ("Despliegue a produccion", "Cierre", "task", start + timedelta(days=110), start + timedelta(days=114), 0, "DevOps", "Pendiente", 0, 8000000),
        ("Cierre administrativo", "Cierre", "task", start + timedelta(days=115), start + timedelta(days=120), 0, "Carlos Mendez", "Pendiente", 0, 3000000),
        ("Lecciones aprendidas", "Cierre", "milestone", start + timedelta(days=121), start + timedelta(days=121), 0, "Carlos Mendez", "Pendiente", 0, 0),
    ]
    task_ids: List[int] = []
    for idx, row in enumerate(rows, start=1):
        cur = conn.execute(
            """INSERT INTO tasks (project_id, title, phase, task_type, start_date, end_date, progress, owner, status, story_points, budget, order_index)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (project_id, row[0], row[1], row[2], row[3].isoformat(), row[4].isoformat(), row[5], row[6], row[7], row[8], row[9], idx),
        )
        task_ids.append(cur.lastrowid)
    component_by_phase = {
        "Inicio": component_ids[2],
        "Planeacion": component_ids[2],
        "Ejecucion": component_ids[1],
        "Pruebas": component_ids[1],
        "Cierre": component_ids[3],
    }
    for task_id, row in zip(task_ids, rows):
        conn.execute("UPDATE tasks SET component_id = ? WHERE id = ?", (component_by_phase.get(row[1], component_ids[0]), task_id))
    dep_pairs = [(3, 4), (6, 8), (8, 9), (9, 10), (10, 11), (11, 12), (12, 13), (13, 14), (14, 15), (15, 16), (16, 17), (17, 18)]
    conn.executemany("INSERT INTO dependencies (project_id, predecessor_id, successor_id, dependency_type) VALUES (?, ?, ?, 'FS')", [(project_id, task_ids[a - 1], task_ids[b - 1]) for a, b in dep_pairs])

    sprints = [
        ("Sprint 1 - Configuraci\u00f3n inicial", "Preparar arquitectura base y pipeline", start + timedelta(days=42), start + timedelta(days=55), "Cerrado", 28),
        ("Sprint 2 - Modulo de Clientes", "Entregar gestion base de clientes", start + timedelta(days=56), start + timedelta(days=69), "En curso", 34),
        ("Sprint 3 - Integraciones", "Conectar APIs y servicios externos", start + timedelta(days=70), start + timedelta(days=83), "Planeado", 34),
    ]
    sprint_ids: List[int] = []
    for s in sprints:
        cur = conn.execute("INSERT INTO sprints (project_id, name, goal, start_date, end_date, status, velocity) VALUES (?, ?, ?, ?, ?, ?, ?)", (project_id, s[0], s[1], s[2].isoformat(), s[3].isoformat(), s[4], s[5]))
        sprint_ids.append(cur.lastrowid)
    stories = [
        (sprint_ids[1], "US-21 Listado de clientes", "En progreso", 5, "Maria Gonzalez", "Alta"),
        (sprint_ids[1], "US-22 Ficha de cliente", "En progreso", 8, "Equipo Dev", "Alta"),
        (sprint_ids[1], "US-23 Busqueda avanzada", "En progreso", 5, "Equipo Dev", "Media"),
        (sprint_ids[1], "US-24 Validar datos de cliente", "Por hacer", 5, "QA Team", "Media"),
        (sprint_ids[1], "US-25 Carga masiva de clientes", "Por hacer", 8, "Equipo Dev", "Alta"),
        (sprint_ids[1], "US-26 Exportar reportes", "Por hacer", 5, "Equipo Dev", "Media"),
        (sprint_ids[0], "US-17 Configuraci\u00f3n inicial", "Hecho", 3, "DevOps", "Alta"),
        (sprint_ids[0], "US-18 Modelos de datos", "Hecho", 8, "Mar\u00eda Gonz\u00e1lez", "Alta"),
        (sprint_ids[0], "US-19 Servicios API", "Hecho", 8, "Equipo Dev", "Alta"),
    ]
    conn.executemany("INSERT INTO stories (project_id, sprint_id, title, status, points, assignee, priority) VALUES (?, ?, ?, ?, ?, ?, ?)", [(project_id, *s) for s in stories])
    risks = [
        ("Retraso por dependencias de integracion", 4, 4, "Asegurar APIs tempranas y ambiente de pruebas", "Abierto", "Maria Gonzalez"),
        ("Capacidad limitada de QA", 3, 4, "Priorizar pruebas criticas y automatizar regresion", "Abierto", "QA Team"),
        ("Cambios de alcance no controlados", 3, 3, "Activar comite de cambios y backlog grooming", "Abierto", "Carlos Mendez"),
        ("Aprobacion tardia del sponsor", 2, 4, "Agendar stage gates desde la planeacion", "Mitigado", "Ana Lopez"),
    ]
    conn.executemany("INSERT INTO risks (project_id, title, probability, impact, level, response, status, owner) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [(project_id, title, prob, impact, risk_level(prob, impact, None), response, status, owner) for title, prob, impact, response, status, owner in risks])
    deliverables = [
        (component_ids[0], "Protocolo de investigacion validado", "Producto de conocimiento", "En revision", "Investigador principal", start + timedelta(days=35), "https://evidencias.local/protocolo", "Documento base del componente cientifico."),
        (component_ids[1], "MVP web Proyecta360", "Entregable", "En progreso", "Equipo tecnologico", start + timedelta(days=80), "https://evidencias.local/mvp", "Plataforma web con gestion hibrida, riesgos y reportes."),
        (component_ids[2], "Matriz de presupuesto y financiador", "Evidencia", "En progreso", "Administrador de fondos", start + timedelta(days=45), "https://evidencias.local/presupuesto", "Soporte para administracion de fondos del proyecto."),
        (component_ids[3], "Resumen ejecutivo mensual", "Producto de conocimiento", "Planeado", "Equipo divulgacion", start + timedelta(days=60), "", "Informe para financiadores y direccion."),
    ]
    conn.executemany(
        """INSERT INTO deliverables (project_id, component_id, name, deliverable_type, status, owner, due_date, evidence_url, description)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [(project_id, component_id, name, dtype, status, owner, due.isoformat(), url, desc) for component_id, name, dtype, status, owner, due, url, desc in deliverables],
    )
    add_history(conn, project_id, "Proyecto", "Proyecta360 LAC", "Creado", "Seed alineado al MVP: componentes, fondos, riesgos, hitos y productos de conocimiento.", "Sistema")
    add_history(conn, project_id, "Documento", "MVP.docx", "Analizado", "Dolor: informacion dispersa; respuesta: fuente unica de avance, riesgos, presupuesto, hitos y resultados.", "Sistema")
    conn.commit()
