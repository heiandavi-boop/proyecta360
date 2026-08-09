from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple


ACTION_TYPES = {
    "no_action",
    "create_task",
    "update_task",
    "create_dependency",
    "create_risk",
    "update_risk",
    "create_deliverable",
    "request_evidence",
    "create_alert",
    "update_project_status",
    "add_mitigation_plan",
    "add_contingency_plan",
}

HEALTH_SUMMARIES = {
    "Saludable": "El proyecto no presenta desviaciones reales y puede mantenerse en seguimiento ordinario.",
    "En observación": "El proyecto presenta señales leves que requieren seguimiento preventivo.",
    "En riesgo": "El proyecto presenta desviaciones relevantes que requieren acciones correctivas.",
    "Crítico": "El proyecto presenta desviaciones acumuladas, contractuales o de alto impacto que requieren escalamiento ejecutivo.",
}


@dataclass(frozen=True)
class Pattern:
    pattern_id: str
    issue_type: str
    metric_key: str
    operator: str
    threshold: int
    action_type: str
    title: str
    priority: str
    target_module: str
    justification_template: str
    expected_impact: str
    risk_if_not_done: str


PATTERNS = [
    Pattern("PAT-001", "schedule_delay", "overdue_tasks", ">", 0, "create_task", "Plan de recuperación para tareas atrasadas", "high", "gantt", "El proyecto tiene {overdue_tasks} tarea(s) atrasada(s), lo que puede afectar el cronograma comprometido.", "Recuperar control del cronograma mediante responsables, fechas objetivo y seguimiento.", "El atraso puede acumularse y comprometer hitos, entregables o fecha contractual."),
    Pattern("PAT-002", "contractual_delay_risk", "contractual_delay_days", ">", 0, "update_project_status", "Marcar proyecto en riesgo por desviación contractual", "high", "project", "La fecha fin calculada supera la fecha contractual en {contractual_delay_days} día(s).", "Visibilizar la desviación para activar gobierno, escalamiento y recuperación.", "El proyecto puede incumplir compromisos contractuales sin escalamiento oportuno."),
    Pattern("PAT-003", "high_risk_without_mitigation", "risks_without_mitigation", ">", 0, "add_mitigation_plan", "Completar plan de mitigación para riesgos altos", "high", "risks", "Hay {risks_without_mitigation} riesgo(s) alto(s) sin plan de mitigación.", "Reducir probabilidad o impacto antes de que el riesgo se materialice.", "El riesgo puede materializarse sin acciones preventivas claras."),
    Pattern("PAT-004", "high_risk_without_contingency", "risks_without_contingency", ">", 0, "add_contingency_plan", "Completar plan de contingencia para riesgos altos", "high", "risks", "Hay {risks_without_contingency} riesgo(s) alto(s) sin plan de contingencia.", "Preparar respuesta concreta si el riesgo se materializa.", "La organización puede reaccionar tarde o de forma improvisada ante el riesgo."),
    Pattern("PAT-005", "budget_progress_deviation", "budget_progress_gap", ">=", 15, "create_risk", "Crear riesgo financiero por desviación presupuesto vs avance", "high", "risks", "El presupuesto ejecutado supera el avance físico en {budget_progress_gap} punto(s) porcentual(es).", "Activar control financiero, revisión de valor ganado y acciones de contención.", "El proyecto puede presentar sobrecosto o avance no evidenciado."),
    Pattern("PAT-006", "missing_evidence", "deliverables_missing_evidence", ">", 0, "request_evidence", "Solicitar evidencia de entregables comprometidos", "medium", "deliverables", "Hay {deliverables_missing_evidence} entregable(s) con evidencia faltante.", "Mejorar trazabilidad, soporte de avance y cierre de entregables.", "El avance puede no ser verificable ante sponsor, auditoría o comité."),
    Pattern("PAT-007", "blocked_dependency", "blocked_dependencies", ">", 0, "create_alert", "Escalar dependencias bloqueantes", "high", "dependencies", "Hay {blocked_dependencies} dependencia(s) bloqueada(s) que pueden afectar la ruta de trabajo.", "Acelerar decisiones y desbloquear tareas sucesoras.", "Las tareas dependientes pueden quedar detenidas y generar atrasos acumulados."),
    Pattern("PAT-008", "resource_overload", "overloaded_resources", ">", 0, "update_task", "Rebalancear capacidad de recursos sobrecargados", "medium", "resources", "Hay {overloaded_resources} recurso(s) sobrecargado(s).", "Reducir cuellos de botella y mejorar cumplimiento de tareas críticas.", "El equipo puede incumplir fechas o bajar calidad por sobreasignación."),
    Pattern("PAT-009", "scope_control_gap", "scope_change_requests", ">", 0, "create_deliverable", "Formalizar acta de control de cambios", "medium", "deliverables", "Existe(n) {scope_change_requests} solicitud(es) de cambio de alcance que requiere(n) formalización y control.", "Controlar impacto en tiempo, costo, alcance y aprobación.", "El alcance puede crecer sin control y generar desviaciones de costo y cronograma."),
    Pattern("PAT-010", "reported_blocker", "conversation_blockers", ">", 0, "create_alert", "Escalar bloqueos reportados en conversaciones", "high", "communications", "Se detectaron {conversation_blockers} bloqueo(s) reportados en conversaciones.", "Convertir señales informales en acciones visibles y trazables.", "Los bloqueos pueden quedarse sin dueño ni seguimiento."),
    Pattern("PAT-011", "sprint_velocity_gap", "sprint_velocity_gap", ">=", 20, "create_task", "Revisar capacidad y alcance del sprint", "medium", "agile", "La brecha de velocidad Scrum es de {sprint_velocity_gap} punto(s).", "Ajustar compromisos del sprint y reducir riesgo de incumplimiento.", "El equipo puede comprometer más trabajo del que puede entregar."),
    Pattern("PAT-012", "high_risk_followup", "high_risks_with_plans", ">", 0, "create_alert", "Seguimiento ejecutivo de riesgos altos", "medium", "risks", "Hay {high_risks_with_plans} riesgo(s) alto(s) activo(s) con mitigación y contingencia definidas.", "Mantener visibilidad ejecutiva sin duplicar planes ya existentes.", "Los riesgos altos pueden perder seguimiento aunque tengan planes definidos."),
    Pattern("PAT-013", "scrum_critical_delay_gap", "scrum_critical_delay_gaps", ">", 0, "create_alert", "Escalar brecha Scrum en tarea critica", "high", "agile", "Hay {scrum_critical_delay_gaps} senal(es) Scrum atrasada(s) vinculada(s) a tarea critica del Plan Maestro.", "Activar seguimiento integrado entre sprint, responsable y ruta critica.", "El atraso agil puede trasladarse a hitos o compromisos del cronograma."),
    Pattern("PAT-014", "critical_task_without_scrum_breakdown", "critical_tasks_without_scrum", ">", 0, "create_alert", "Desglosar tareas criticas en historias Scrum", "medium", "agile", "Hay {critical_tasks_without_scrum} tarea(s) critica(s) sin historias Scrum asociadas.", "Mejorar trazabilidad entre gobierno del plan y ejecucion agil.", "La tarea critica puede avanzar sin evidencia granular de ejecucion."),
    Pattern("PAT-015", "scrum_progress_gap", "scrum_progress_gap", ">=", 20, "create_alert", "Revisar avance Scrum frente al Plan Maestro", "medium", "agile", "El avance Scrum vinculado esta {scrum_progress_gap} punto(s) por debajo de lo esperado por fecha.", "Corregir desfase entre avance iterativo y compromiso del cronograma.", "El equipo puede reportar avance parcial sin recuperar la fecha comprometida."),
]


def analyze_project_internal_ai(project_snapshot: dict) -> dict:
    metrics = build_internal_metrics(project_snapshot)
    context = project_snapshot.get("project_context") or (project_snapshot.get("project") or {}).get("ai_context") or {}
    issues, triggered = [], []
    for pattern in PATTERNS:
        if not applies(pattern, metrics):
            continue
        triggered.append(pattern)
        issues.append(issue_from_pattern(pattern, metrics))
    health = classify_from_metrics(metrics, issues)
    raw_actions = []
    for pattern in triggered:
        raw_actions.append(action_from_pattern(pattern, metrics, project_snapshot, health))
    actions, duplicates_merged = deduplicate_actions(raw_actions)
    if not actions:
        actions = [no_action()]
    return {
        "project_health": health,
        "summary": summary_for_health(health, metrics, len(issues), len(actions), context),
        "detected_issues": issues,
        "recommended_actions": actions,
        "mode": "internal_rules",
        "engine_label": "Motor IA interno v1",
        "quality_metadata": {
            "issue_count": len(issues),
            "duplicates_merged": duplicates_merged,
            "classified_by_metrics": health,
            "metrics": metrics,
            "source": "training_standalone_v5_rules",
        },
    }


def base_metrics() -> Dict[str, int]:
    return {
        "overall_progress": 0,
        "budget_execution": 0,
        "budget_progress_gap": 0,
        "overdue_tasks": 0,
        "critical_tasks": 0,
        "high_risks": 0,
        "risks_without_mitigation": 0,
        "risks_without_contingency": 0,
        "high_risks_with_plans": 0,
        "blocked_dependencies": 0,
        "deliverables_missing_evidence": 0,
        "overloaded_resources": 0,
        "scope_change_requests": 0,
        "conversation_blockers": 0,
        "sprint_velocity_gap": 0,
        "scrum_critical_delay_gaps": 0,
        "critical_tasks_without_scrum": 0,
        "scrum_progress_gap": 0,
        "contractual_delay_days": 0,
    }


def build_internal_metrics(snapshot: Dict[str, Any]) -> Dict[str, int]:
    metrics = base_metrics()
    incoming = snapshot.get("metrics") or {}
    metrics["overall_progress"] = intish(incoming.get("overall_progress", incoming.get("progress", 0)))
    budget = floatish(incoming.get("budget", (snapshot.get("project") or {}).get("budget", 0)))
    spent = floatish(incoming.get("spent", 0))
    metrics["budget_execution"] = int(round(floatish(incoming.get("budget_execution", (spent / budget * 100) if budget > 0 else 0))))
    metrics["budget_progress_gap"] = max(
        0,
        int(round(floatish(incoming.get("budget_progress_gap", metrics["budget_execution"] - metrics["overall_progress"])))),
    )
    metrics["overdue_tasks"] = intish(incoming.get("overdue_tasks", incoming.get("delayed_tasks", 0)))
    metrics["critical_tasks"] = intish(incoming.get("critical_tasks", incoming.get("critical_path_tasks", 0)))
    metrics["high_risks"] = intish(incoming.get("high_risks", 0))
    metrics["risks_without_mitigation"] = intish(incoming.get("risks_without_mitigation", 0))
    metrics["risks_without_contingency"] = intish(incoming.get("risks_without_contingency", 0))
    metrics["high_risks_with_plans"] = intish(incoming.get("high_risks_with_plans", 0))
    metrics["blocked_dependencies"] = intish(incoming.get("blocked_dependencies", 0))
    metrics["deliverables_missing_evidence"] = intish(incoming.get("deliverables_missing_evidence", 0))
    metrics["overloaded_resources"] = intish(incoming.get("overloaded_resources", 0))
    metrics["scope_change_requests"] = scope_change_requests(snapshot, incoming)
    metrics["conversation_blockers"] = intish(incoming.get("conversation_blockers", 0))
    metrics["sprint_velocity_gap"] = intish(incoming.get("sprint_velocity_gap", 0))
    metrics["contractual_delay_days"] = contractual_delay_days(snapshot, incoming)

    today = str(snapshot.get("today") or date.today().isoformat())
    tasks = snapshot.get("tasks") or []
    if tasks and not metrics["overdue_tasks"]:
        overdue = [t for t in tasks if is_open(t) and str(t.get("end_date") or "")[:10] < today and str(t.get("task_type") or "") != "summary"]
        metrics["overdue_tasks"] = len(overdue)
    if tasks and not metrics["critical_tasks"]:
        metrics["critical_tasks"] = len([t for t in tasks if truthy(t.get("is_critical")) or truthy(t.get("critical"))])

    risks = snapshot.get("risks") or []
    if risks:
        high = [r for r in risks if is_high_risk(r) and str(r.get("status") or "").lower() != "cerrado"]
        metrics["high_risks"] = len(high)
        metrics["risks_without_mitigation"] = len([r for r in high if not str(r.get("mitigation_plan") or "").strip()])
        metrics["risks_without_contingency"] = len([r for r in high if not str(r.get("contingency_plan") or "").strip()])
        metrics["high_risks_with_plans"] = len([r for r in high if str(r.get("mitigation_plan") or "").strip() and str(r.get("contingency_plan") or "").strip()])

    deliverables = snapshot.get("deliverables") or []
    if deliverables and not metrics["deliverables_missing_evidence"]:
        metrics["deliverables_missing_evidence"] = len([
            d for d in deliverables
            if str(d.get("due_date") or "")[:10] <= today
            and str(d.get("status") or "") not in {"Aprobado", "Cerrado"}
            and not str(d.get("evidence_url") or d.get("evidence_id") or "").strip()
        ])

    dependencies = snapshot.get("dependencies") or []
    if dependencies and not metrics["blocked_dependencies"]:
        metrics["blocked_dependencies"] = len([d for d in dependencies if truthy(d.get("blocked")) or str(d.get("status") or "").lower() in {"bloqueada", "blocked"}])

    resources = snapshot.get("resources") or []
    if resources and not metrics["overloaded_resources"]:
        metrics["overloaded_resources"] = len([r for r in resources if intish(r.get("allocation_pct", r.get("capacity_used", r.get("load", 0)))) > 100])

    conversations = snapshot.get("conversations") or []
    if conversations and not metrics["conversation_blockers"]:
        blocker_words = ["bloque", "impedimento", "critico", "crítico", "urgente"]
        metrics["conversation_blockers"] = len([c for c in conversations if any(word in str(c.get("message", "")).lower() for word in blocker_words)])

    sprints = snapshot.get("sprints") or []
    stories = snapshot.get("stories") or []
    if not metrics["sprint_velocity_gap"] and sprints:
        velocity = max([intish(s.get("velocity", 0)) for s in sprints] or [0])
        open_points = sum(intish(s.get("points", 0)) for s in stories if str(s.get("status") or "").lower() != "hecho")
        metrics["sprint_velocity_gap"] = max(0, open_points - velocity)
    if tasks and stories:
        enrich_scrum_master_plan_metrics(metrics, tasks, stories, sprints, today)
    elif tasks:
        metrics["critical_tasks_without_scrum"] = len([t for t in tasks if is_scrum_task(t) and task_is_critical(t)])
    return metrics


def enrich_scrum_master_plan_metrics(metrics: Dict[str, int], tasks: List[Dict[str, Any]], stories: List[Dict[str, Any]], sprints: List[Dict[str, Any]], today: str) -> None:
    by_task: Dict[int, List[Dict[str, Any]]] = {}
    for story in stories:
        task_id = intish(story.get("master_task_id"))
        if task_id:
            by_task.setdefault(task_id, []).append(story)
    sprints_by_id = {intish(s.get("id")): s for s in sprints}
    delay_gaps = 0
    progress_gaps: List[int] = []
    missing_breakdown = 0
    for task in tasks:
        task_id = intish(task.get("id"))
        linked = by_task.get(task_id, [])
        if task_is_critical(task) and is_scrum_task(task) and not linked:
            missing_breakdown += 1
        if not linked:
            continue
        if task_is_critical(task):
            for story in linked:
                sprint = sprints_by_id.get(intish(story.get("sprint_id")))
                sprint_overdue = bool(sprint and str(sprint.get("end_date") or "")[:10] < today and is_open(sprint))
                story_blocked = str(story.get("status") or "").lower() in {"bloqueada", "blocked"}
                if not done_story(story) and (sprint_overdue or story_blocked):
                    delay_gaps += 1
        expected = expected_task_progress(task, today)
        scrum = linked_scrum_progress(linked)
        if expected - scrum >= 20:
            progress_gaps.append(expected - scrum)
    metrics["scrum_critical_delay_gaps"] = delay_gaps
    metrics["critical_tasks_without_scrum"] = missing_breakdown
    metrics["scrum_progress_gap"] = max(progress_gaps or [0])


def linked_scrum_progress(stories: List[Dict[str, Any]]) -> int:
    total_points = sum(intish(story.get("points")) for story in stories)
    done_points = sum(intish(story.get("points")) for story in stories if done_story(story))
    if total_points:
        return int(round(done_points / total_points * 100))
    return int(round(len([story for story in stories if done_story(story)]) / len(stories) * 100)) if stories else 0


def expected_task_progress(task: Dict[str, Any], today: str) -> int:
    start = str(task.get("start_date") or "")[:10]
    end = str(task.get("end_date") or start)[:10]
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
        today_date = date.fromisoformat(today[:10])
    except ValueError:
        return intish(task.get("progress"))
    if today_date <= start_date:
        return 0
    if today_date >= end_date:
        return 100
    total = max(1, (end_date - start_date).days)
    elapsed = max(0, (today_date - start_date).days)
    return int(round(elapsed / total * 100))


def task_is_critical(task: Dict[str, Any]) -> bool:
    status = str(task.get("status") or "").lower()
    return truthy(task.get("is_critical")) or truthy(task.get("critical")) or "crit" in status or "crít" in status or "riesgo" in status


def is_scrum_task(task: Dict[str, Any]) -> bool:
    text = " ".join(str(task.get(key) or "") for key in ("methodology", "phase", "description", "title")).lower()
    return "scrum" in text or "sprint" in text or "historia" in text


def done_story(story: Dict[str, Any]) -> bool:
    return str(story.get("status") or "").lower() in {"hecho", "done", "completado", "cerrado"}


def scope_change_requests(snapshot: Dict[str, Any], incoming: Dict[str, Any]) -> int:
    if "scope_change_requests" in incoming:
        return intish(incoming.get("scope_change_requests"))
    project = snapshot.get("project") or {}
    params = project.get("parameters") or {}
    for source in (project, params, params.get("governance") or {}):
        if "scope_change_requests" in source:
            return intish(source.get("scope_change_requests"))
    return 0


def contractual_delay_days(snapshot: Dict[str, Any], incoming: Dict[str, Any]) -> int:
    if "contractual_delay_days" in incoming:
        return intish(incoming.get("contractual_delay_days"))
    project = snapshot.get("project") or {}
    calculated = project.get("calculated_end_date") or project.get("end_date")
    contractual = project.get("contractual_end_date")
    try:
        if calculated and contractual:
            return max(0, (date.fromisoformat(str(calculated)[:10]) - date.fromisoformat(str(contractual)[:10])).days)
    except ValueError:
        return 0
    return 0


def applies(pattern: Pattern, metrics: Dict[str, int]) -> bool:
    value = metrics.get(pattern.metric_key, 0)
    if pattern.operator == ">=":
        return value >= pattern.threshold
    return value > pattern.threshold


def issue_from_pattern(pattern: Pattern, metrics: Dict[str, int]) -> Dict[str, Any]:
    return {
        "type": pattern.issue_type,
        "severity": severity_for_priority(pattern.priority),
        "description": pattern.justification_template.format(**metrics),
        "related_entity_type": related_entity_type(pattern.target_module),
        "related_entity_id": None,
        "source_pattern_id": pattern.pattern_id,
    }


def action_from_pattern(pattern: Pattern, metrics: Dict[str, int], snapshot: Dict[str, Any], project_health: str = "") -> Dict[str, Any]:
    title = title_for_pattern(pattern, project_health)
    payload = proposed_payload(pattern, snapshot, title, project_health)
    return {
        "action_type": pattern.action_type,
        "target_module": pattern.target_module,
        "target_entity_type": related_entity_type(pattern.target_module),
        "target_entity_id": payload.get("task_id") or payload.get("risk_id") or payload.get("deliverable_id"),
        "title": title,
        "description": description_for(pattern),
        "justification": pattern.justification_template.format(**metrics),
        "expected_impact": pattern.expected_impact,
        "risk_if_not_done": pattern.risk_if_not_done,
        "priority": pattern.priority,
        "requires_human_approval": True,
        "status": "Pendiente",
        "proposed_payload": payload,
        "source_pattern_id": pattern.pattern_id,
        "source_issue_type": pattern.issue_type,
    }


def proposed_payload(pattern: Pattern, snapshot: Dict[str, Any], title: str, project_health: str = "") -> Dict[str, Any]:
    project = snapshot.get("project") or {}
    owner = project.get("project_manager") or "Project Manager"
    if pattern.action_type == "create_task":
        return {"title": title, "duration_days": 3, "owner": owner, "status": "Pendiente", "progress": 0, "description": pattern.expected_impact}
    if pattern.action_type == "update_project_status":
        status = "Crítico" if project_health == "Crítico" else "En riesgo"
        return {"status": status, "message": title}
    if pattern.action_type == "create_risk":
        return {"title": title, "probability": 3, "impact": 4, "response": "Mitigar", "owner": owner, "status": "Abierto", "mitigation_plan": "Revisar brecha entre presupuesto ejecutado y avance físico."}
    if pattern.action_type in {"add_mitigation_plan", "add_contingency_plan", "update_risk"}:
        risk = first_high_risk(snapshot)
        field = "mitigation_plan" if pattern.action_type == "add_mitigation_plan" else "contingency_plan"
        return {"risk_id": risk.get("id") if risk else None, field: pattern.expected_impact, "plan": pattern.expected_impact}
    if pattern.action_type == "request_evidence":
        deliverable = first_missing_evidence(snapshot)
        return {"deliverable_id": deliverable.get("id") if deliverable else None, "description": "Cargar evidencia de avance, aprobación o entrega.", "message": title}
    if pattern.action_type == "create_deliverable":
        return {"name": title, "deliverable_type": "Acta de control", "status": "Planeado", "owner": owner, "description": pattern.justification_template}
    if pattern.action_type == "update_task":
        task = first_open_task(snapshot)
        return {"task_id": task.get("id") if task else None, "owner": owner, "description": pattern.expected_impact}
    if pattern.action_type == "create_alert":
        return {"message": title, "priority": pattern.priority}
    return {}


def deduplicate_actions(actions: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    merged: Dict[str, Dict[str, Any]] = {}
    duplicate_count = 0
    for action in actions:
        key = action["action_type"]
        if key not in ACTION_TYPES:
            continue
        if key not in merged:
            merged[key] = dict(action)
            continue
        duplicate_count += 1
        current = merged[key]
        if priority_rank(action.get("priority", "")) > priority_rank(current.get("priority", "")):
            merged[key] = {**action}
            current = merged[key]
        for field in ("justification", "expected_impact", "risk_if_not_done"):
            value = action.get(field, "")
            if value and value not in current.get(field, ""):
                current[field] = f"{current.get(field, '')} | {value}".strip(" |")
        for field in ("source_pattern_id", "source_issue_type"):
            value = str(action.get(field, ""))
            if value and value not in current.get(field, ""):
                current[field] = f"{current.get(field, '')}|{value}".strip("|")
        if "acción consolidada" not in current["title"]:
            current["title"] = f"{current['title']} / acción consolidada"
    result = sorted(merged.values(), key=lambda item: (-priority_rank(item.get("priority", "")), item["action_type"]))
    if len(result) > 1:
        result = [item for item in result if item["action_type"] != "no_action"]
    return result, duplicate_count


def classify_from_metrics(metrics: Dict[str, int], issues: List[Dict[str, Any]]) -> str:
    issue_total = len(issues)
    if issue_total == 0:
        return "Saludable"
    if is_critical_combination(metrics) or issue_total >= 8:
        return "Crítico"
    if issue_total >= 3:
        return "En riesgo"
    return "En observación"


def is_critical_combination(metrics: Dict[str, int]) -> bool:
    strong_contractual = metrics["contractual_delay_days"] >= 10
    strong_schedule = metrics["overdue_tasks"] >= 4 and metrics["critical_tasks"] >= 3
    strong_risk = metrics["high_risks"] >= 3 and (metrics["risks_without_mitigation"] >= 1 or metrics["risks_without_contingency"] >= 1)
    strong_block = metrics["blocked_dependencies"] >= 2 or metrics["conversation_blockers"] >= 1
    financial = metrics["budget_progress_gap"] >= 20
    return (strong_contractual and strong_schedule and strong_risk) or (strong_schedule and strong_risk and strong_block and financial)


def no_action() -> Dict[str, Any]:
    return {
        "action_type": "no_action",
        "target_module": "project",
        "target_entity_type": "project",
        "target_entity_id": None,
        "title": "Mantener seguimiento ordinario del proyecto",
        "description": "No se detectan desviaciones reales que requieran acción correctiva.",
        "justification": "No se detectan desviaciones reales que requieran acción correctiva.",
        "expected_impact": "Mantener trazabilidad sin generar tareas innecesarias.",
        "risk_if_not_done": "Riesgo bajo; mantener seguimiento periódico.",
        "priority": "low",
        "requires_human_approval": True,
        "status": "Pendiente",
        "proposed_payload": {},
        "source_pattern_id": "NO-ACTION",
        "source_issue_type": "none",
    }


def summary_for_health(health: str, metrics: Dict[str, int], issue_count: int, action_count: int) -> str:
    return (
        f"{HEALTH_SUMMARIES[health]} Avance {metrics['overall_progress']}%, "
        f"presupuesto ejecutado {metrics['budget_execution']}%, {metrics['overdue_tasks']} tarea(s) atrasada(s), "
        f"{metrics['high_risks']} riesgo(s) alto(s), {metrics['deliverables_missing_evidence']} entregable(s) sin evidencia. "
        f"Se detectaron {issue_count} hallazgo(s) y se generaron {action_count} recomendación(es) pendiente(s) de aprobación humana."
    )


def summary_for_health(health: str, metrics: Dict[str, int], issue_count: int, action_count: int, context: Optional[Dict[str, Any]] = None) -> str:
    context = context or {}
    objective = str(context.get("general_objective") or "").strip()
    project_context = str(context.get("context") or "").strip()
    context_sentence = ""
    if objective:
        context_sentence += f" Objetivo analizado: {objective[:180]}."
    if project_context:
        context_sentence += f" Contexto relevante: {project_context[:180]}."
    return (
        f"{HEALTH_SUMMARIES[health]} Avance {metrics['overall_progress']}%, "
        f"presupuesto ejecutado {metrics['budget_execution']}%, {metrics['overdue_tasks']} tarea(s) atrasada(s), "
        f"{metrics['high_risks']} riesgo(s) alto(s), {metrics['deliverables_missing_evidence']} entregable(s) sin evidencia. "
        f"Se detectaron {issue_count} hallazgo(s) y se generaron {action_count} recomendacion(es) pendiente(s) de aprobacion humana."
        f"{context_sentence}"
    )


def severity_for_priority(priority: str) -> str:
    return "critical" if priority == "critical" else "high" if priority == "high" else "medium" if priority == "medium" else "low"


def priority_rank(priority: str) -> int:
    return {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(priority, 0)


def related_entity_type(module: str) -> str:
    return {
        "gantt": "task",
        "risks": "risk",
        "deliverables": "deliverable",
        "dependencies": "dependency",
        "resources": "resource",
        "agile": "project",
        "communications": "project",
        "project": "project",
    }.get(module, "project")


def description_for(pattern: Pattern) -> str:
    return f"Acción propuesta por el Motor IA interno v1 para atender {pattern.issue_type}."


def title_for_pattern(pattern: Pattern, project_health: str) -> str:
    if pattern.issue_type == "contractual_delay_risk" and project_health == "Crítico":
        return "Escalar proyecto a estado Crítico"
    return pattern.title


def first_high_risk(snapshot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return next((r for r in snapshot.get("risks", []) if is_high_risk(r) and str(r.get("status") or "").lower() != "cerrado"), None)


def first_missing_evidence(snapshot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    today = str(snapshot.get("today") or date.today().isoformat())
    return next((d for d in snapshot.get("deliverables", []) if str(d.get("due_date") or "")[:10] <= today and not str(d.get("evidence_url") or "").strip()), None)


def first_open_task(snapshot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return next((t for t in snapshot.get("tasks", []) if is_open(t) and str(t.get("task_type") or "") != "summary"), None)


def is_high_risk(risk: Dict[str, Any]) -> bool:
    level = str(risk.get("level") or "").lower()
    return level in {"alto", "high"} or intish(risk.get("probability", 0)) * intish(risk.get("impact", 0)) >= 15


def is_open(item: Dict[str, Any]) -> bool:
    return str(item.get("status") or "").lower() not in {"completada", "completado", "cerrada", "cerrado", "hecho", "done"}


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "si", "sí", "y"}


def intish(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except Exception:
        return default


def floatish(value: Any, default: float = 0) -> float:
    try:
        return float(str(value).strip())
    except Exception:
        return default
