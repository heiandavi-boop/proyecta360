from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from proyecta360.services.project_schedule import critical_path_task_ids


def _parse_date(value: Any, fallback: date) -> date:
    try:
        return date.fromisoformat(str(value or fallback.isoformat()))
    except ValueError:
        return fallback


def _task_duration(task: Dict[str, Any], fallback: date) -> int:
    start = _parse_date(task.get("start_date"), fallback)
    end = _parse_date(task.get("end_date", task.get("start_date")), fallback)
    return max(1, (end - start).days + 1)


def _expected_task_progress(task: Dict[str, Any], current_date: date) -> float:
    start = _parse_date(task.get("start_date"), current_date)
    end = _parse_date(task.get("end_date", task.get("start_date")), current_date)
    if current_date < start:
        return 0.0
    if current_date >= end:
        return 100.0
    return max(0.0, min(100.0, ((current_date - start).days + 1) / _task_duration(task, current_date) * 100))


def _schedule_score(work_tasks: List[Dict[str, Any]], current_day: str, progress_variance_pp: float) -> tuple[float, int]:
    due_milestones = [t for t in work_tasks if t.get("task_type") == "milestone" and str(t.get("end_date", "")) <= current_day]
    due_activities = [t for t in work_tasks if t.get("task_type") != "milestone" and str(t.get("end_date", "")) <= current_day]
    completed_due_milestones = [t for t in due_milestones if int(t.get("progress") or 0) >= 100]
    completed_due_activities = [t for t in due_activities if int(t.get("progress") or 0) >= 100]
    milestone_score = round(len(completed_due_milestones) / len(due_milestones) * 100, 1) if due_milestones else None
    activity_score = round(len(completed_due_activities) / len(due_activities) * 100, 1) if due_activities else None
    if milestone_score is None and activity_score is None:
        score = max(0.0, min(100.0, round(100 + progress_variance_pp, 1)))
    elif milestone_score is None:
        score = float(activity_score or 0)
    elif activity_score is None:
        score = float(milestone_score)
    else:
        score = round((milestone_score * 0.6) + (activity_score * 0.4), 1)
    at_risk_milestones = len([m for m in due_milestones if int(m.get("progress") or 0) < 100])
    return score, at_risk_milestones


def _budget_score(budget_variance_pp: float) -> int:
    if budget_variance_pp <= 0:
        return 100
    if budget_variance_pp <= 5:
        return 90
    if budget_variance_pp <= 10:
        return 75
    if budget_variance_pp <= 20:
        return 55
    return 30


def _risk_score(risks: List[Dict[str, Any]]) -> int:
    active_risks = [r for r in risks if r.get("status") != "Cerrado"]
    has_active_materialized = any(str(r.get("status", "")).lower() == "materializado" for r in active_risks)
    max_level = max((int(r.get("probability") or 0) * int(r.get("impact") or 0) for r in active_risks), default=0)
    if has_active_materialized:
        return 20
    if max_level >= 17:
        return 40
    if max_level >= 10:
        return 65
    if max_level >= 5:
        return 90
    return 100


def calculate_metrics(
    project: Dict[str, Any],
    tasks: List[Dict[str, Any]],
    risks: List[Dict[str, Any]],
    stories: List[Dict[str, Any]],
    dependencies: List[Dict[str, Any]],
    budget_entries: List[Dict[str, Any]] | None = None,
    today: str | None = None,
) -> Dict[str, Any]:
    work_tasks = [t for t in tasks if t["task_type"] != "summary"]
    current_day = today or date.today().isoformat()
    current_date = date.fromisoformat(current_day)
    total_weight = sum(_task_duration(t, current_date) for t in work_tasks) or 1
    progress = round(sum(int(t["progress"] or 0) * _task_duration(t, current_date) for t in work_tasks) / total_weight, 1) if work_tasks else 0
    expected_progress = round(sum(_expected_task_progress(t, current_date) * _task_duration(t, current_date) for t in work_tasks) / total_weight, 1) if work_tasks else 0
    progress_variance_pp = round(progress - expected_progress, 1)
    budget_total = float(project["budget"] or 0)
    budget_entries = budget_entries or []
    cumulative_budget_entries = [entry for entry in budget_entries if str(entry.get("month", "")) <= current_day[:7]]
    total_planned_budget = round(sum(float(entry.get("planned_amount") or 0) for entry in budget_entries), 2)
    planned_spent = round(sum(float(entry.get("planned_amount") or 0) for entry in cumulative_budget_entries), 2)
    spent = round(sum(float(entry.get("executed_amount") or 0) for entry in cumulative_budget_entries), 2)
    budget_source = "plan_mensual" if budget_entries else "estimado_tareas"
    if not budget_entries:
        spent = round(sum(float(t["budget"] or 0) * int(t["progress"] or 0) / 100 for t in work_tasks), 2)
        planned_spent = round(budget_total * expected_progress / 100, 2)
        total_planned_budget = budget_total
    budget_executed_percent = round((spent / budget_total) * 100, 1) if budget_total else 0
    budget_expected_percent = round(expected_progress, 1) if budget_total else 0
    if budget_entries and budget_total:
        budget_expected_percent = round((planned_spent / budget_total) * 100, 1)
    budget_variance_pp = round(budget_executed_percent - budget_expected_percent, 1)
    schedule_score, at_risk_milestones = _schedule_score(work_tasks, current_day, progress_variance_pp)
    budget_score = _budget_score(budget_variance_pp)
    risk_score = _risk_score(risks)
    phs = round((schedule_score * 0.45) + (budget_score * 0.30) + (risk_score * 0.25), 1)
    health = "Saludable"
    if phs < 80:
        health = "En riesgo"
    if phs < 60:
        health = "Critico"
    high_risks = len([r for r in risks if r["level"] in {"Alto", "Critico"} and r["status"] != "Cerrado"])
    open_risks = len([r for r in risks if r["status"] != "Cerrado"])
    completed_points = sum(int(s["points"] or 0) for s in stories if s["status"] == "Hecho")
    total_points = sum(int(s["points"] or 0) for s in stories) or 1
    delayed_tasks = [
        t for t in work_tasks
        if str(t["end_date"]) < current_day and int(t["progress"] or 0) < 100 and t["task_type"] != "milestone"
    ]
    critical_ids = critical_path_task_ids(tasks, dependencies)
    critical_open = [t for t in work_tasks if t["id"] in critical_ids and int(t["progress"] or 0) < 100]
    next_milestone = next(
        (t for t in sorted([t for t in work_tasks if t.get("task_type") == "milestone" and str(t.get("end_date", "")) >= current_day], key=lambda t: str(t.get("end_date", "")))),
        None,
    )
    return {
        "progress": progress,
        "expected_progress": expected_progress,
        "progress_variance_pp": progress_variance_pp,
        "schedule_score": schedule_score,
        "budget_score": budget_score,
        "risk_score": risk_score,
        "phs": phs,
        "budget": budget_total,
        "spent": spent,
        "planned_spent": planned_spent,
        "total_planned_budget": total_planned_budget,
        "budget_source": budget_source,
        "budget_executed_percent": budget_executed_percent,
        "budget_expected_percent": budget_expected_percent,
        "budget_variance_pp": budget_variance_pp,
        "remaining_budget": max(budget_total - spent, 0),
        "open_risks": open_risks,
        "high_risks": high_risks,
        "critical_path_tasks": len(critical_open),
        "delayed_tasks": len(delayed_tasks),
        "at_risk_milestones": at_risk_milestones,
        "next_milestone": {"title": next_milestone.get("title"), "end_date": next_milestone.get("end_date")} if next_milestone else None,
        "story_completion": round(completed_points / total_points * 100, 1),
        "health": health,
    }


def portfolio_item(project: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "project_id": project["id"],
        "name": project["name"],
        "project_manager": project["project_manager"],
        "methodology": project["methodology"],
        "status": project["status"],
        "start_date": project["start_date"],
        "end_date": project["end_date"],
        "contractual_end_date": project.get("contractual_end_date", ""),
        "budget": float(project["budget"] or 0),
        "currency": project["currency"],
        "progress": metrics["progress"],
        "expected_progress": metrics["expected_progress"],
        "progress_variance_pp": metrics["progress_variance_pp"],
        "spent": metrics["spent"],
        "planned_spent": metrics["planned_spent"],
        "total_planned_budget": metrics["total_planned_budget"],
        "budget_source": metrics["budget_source"],
        "budget_executed_percent": metrics["budget_executed_percent"],
        "budget_expected_percent": metrics["budget_expected_percent"],
        "budget_variance_pp": metrics["budget_variance_pp"],
        "open_risks": metrics["open_risks"],
        "high_risks": metrics["high_risks"],
        "critical_path_tasks": metrics["critical_path_tasks"],
        "at_risk_milestones": metrics["at_risk_milestones"],
        "next_milestone": metrics["next_milestone"],
        "phs": metrics["phs"],
        "schedule_score": metrics["schedule_score"],
        "budget_score": metrics["budget_score"],
        "risk_score": metrics["risk_score"],
        "health": metrics["health"],
    }


def project_intelligence(
    metrics: Dict[str, Any],
    risks: List[Dict[str, Any]],
    milestones: List[Dict[str, Any]],
    deliverables: List[Dict[str, Any]],
    today: str | None = None,
) -> Dict[str, Any]:
    current_day = today or date.today().isoformat()
    compromised_milestones = [m for m in milestones if m["end_date"] <= current_day and int(m["progress"] or 0) < 100]
    due_deliverables = [
        d for d in deliverables
        if d["due_date"] and d["due_date"] <= current_day and d["status"] not in {"Aprobado", "Cerrado"}
    ]
    recommendations = []
    if metrics["progress_variance_pp"] < -5:
        recommendations.append("Revisar actividades que explican la desviacion frente al avance esperado.")
    if metrics["budget_variance_pp"] > 5:
        recommendations.append("Revisar sobreejecucion presupuestal frente al plan acumulado.")
    if metrics["high_risks"]:
        recommendations.append("Revisar riesgos altos o criticos y confirmar planes de respuesta.")
    if compromised_milestones:
        recommendations.append("Escalar hitos comprometidos con sponsor y responsables.")
    if due_deliverables:
        recommendations.append("Cerrar evidencias de entregables vencidos o reprogramarlos.")
    if not recommendations:
        recommendations.append("Mantener seguimiento semanal y registrar evidencia de avance.")
    return {
        "status": metrics["health"],
        "detected_risks": risks,
        "compromised_milestones": compromised_milestones,
        "due_deliverables": due_deliverables,
        "recommendations": recommendations,
    }
