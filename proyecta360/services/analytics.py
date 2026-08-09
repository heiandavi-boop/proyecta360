from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from proyecta360.services.project_schedule import critical_path_task_ids


def calculate_metrics(
    project: Dict[str, Any],
    tasks: List[Dict[str, Any]],
    risks: List[Dict[str, Any]],
    stories: List[Dict[str, Any]],
    dependencies: List[Dict[str, Any]],
    today: str | None = None,
) -> Dict[str, Any]:
    work_tasks = [t for t in tasks if t["task_type"] != "summary"]
    progress = round(sum(int(t["progress"] or 0) for t in work_tasks) / len(work_tasks), 1) if work_tasks else 0
    spent = round(sum(float(t["budget"] or 0) * int(t["progress"] or 0) / 100 for t in work_tasks), 2)
    high_risks = len([r for r in risks if r["level"] == "Alto" and r["status"] != "Cerrado"])
    open_risks = len([r for r in risks if r["status"] != "Cerrado"])
    completed_points = sum(int(s["points"] or 0) for s in stories if s["status"] == "Hecho")
    total_points = sum(int(s["points"] or 0) for s in stories) or 1
    current_day = today or date.today().isoformat()
    delayed_tasks = [
        t for t in work_tasks
        if t["end_date"] < current_day and int(t["progress"] or 0) < 100 and t["task_type"] != "milestone"
    ]
    critical_ids = critical_path_task_ids(tasks, dependencies)
    critical_open = [t for t in work_tasks if t["id"] in critical_ids and int(t["progress"] or 0) < 100]
    health = "Saludable"
    if high_risks >= 2 or len(delayed_tasks) >= 3:
        health = "En riesgo"
    if high_risks >= 4 or len(delayed_tasks) >= 6:
        health = "Crítico"
    return {
        "progress": progress,
        "budget": float(project["budget"] or 0),
        "spent": spent,
        "remaining_budget": max(float(project["budget"] or 0) - spent, 0),
        "open_risks": open_risks,
        "high_risks": high_risks,
        "critical_path_tasks": len(critical_open),
        "delayed_tasks": len(delayed_tasks),
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
        "spent": metrics["spent"],
        "open_risks": metrics["open_risks"],
        "high_risks": metrics["high_risks"],
        "critical_path_tasks": metrics["critical_path_tasks"],
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
    if metrics["delayed_tasks"]:
        recommendations.append("Priorizar actividades atrasadas antes del siguiente comite.")
    if metrics["high_risks"]:
        recommendations.append("Revisar riesgos altos y confirmar plan de contingencia.")
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
