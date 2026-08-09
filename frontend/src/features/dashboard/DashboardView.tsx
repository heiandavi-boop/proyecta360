import { AlertTriangle, CalendarDays, CircleDollarSign, ListChecks, TrendingUp } from "lucide-react";

import type { BootstrapPayload, ProjectMetrics } from "@/domain/project";
import { useI18n } from "@/i18n/i18n";

type DashboardViewProps = {
  data: BootstrapPayload;
};

function money(value: number, currency: string) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value) + " " + currency;
}

function kpis(metrics: ProjectMetrics, currency: string) {
  return [
    { icon: TrendingUp, label: "kpi.progress", value: `${metrics.progress}%`, detail: "common.completed" },
    { icon: CalendarDays, label: "kpi.calculatedEnd", value: "", detail: "kpi.currentPlan" },
    { icon: AlertTriangle, label: "kpi.openRisks", value: String(metrics.open_risks), detail: "common.high" },
    { icon: ListChecks, label: "kpi.criticalPath", value: String(metrics.critical_path_tasks), detail: "common.tasks" },
    { icon: CircleDollarSign, label: "kpi.executedBudget", value: money(metrics.spent, currency), detail: "ai.budget" }
  ];
}

export function DashboardView({ data }: DashboardViewProps) {
  return (
    <>
      <ProjectKpis data={data} />
      <ProjectSnapshot data={data} />
    </>
  );
}

export function ProjectKpis({ data }: DashboardViewProps) {
  const { t } = useI18n();
  const project = data.current_project;
  const metrics = data.metrics;
  const rows = kpis(metrics, project.currency);
  rows[1].value = project.end_date;

  return (
    <section className="kpi-grid">
      {rows.map((item) => {
        const Icon = item.icon;
        return (
          <article className="kpi-card" key={item.label}>
            <Icon aria-hidden size={28} />
            <div>
              <span>{t(item.label)}</span>
              <strong>{item.value}</strong>
              <small>{t(item.detail)}</small>
            </div>
          </article>
        );
      })}
    </section>
  );
}

function ProjectSnapshot({ data }: DashboardViewProps) {
  const { t } = useI18n();

  return (
    <section className="dashboard-grid">
      <article className="panel">
        <h2>{t("portfolio.title")}</h2>
        <div className="project-list">
          {data.portfolio.slice(0, 8).map((item, index) => (
            <div className="project-row" key={`${String(item.name)}-${index}`}>
              <b>{String(item.name || "")}</b>
              <span>{String(item.health || "")}</span>
              <span>{String(item.progress || 0)}%</span>
            </div>
          ))}
        </div>
      </article>
      <article className="panel">
        <h2>{t("gantt.title")}</h2>
        <div className="task-list">
          {data.tasks.slice(0, 8).map((task) => (
            <div className="task-row" key={task.id}>
              <b>{task.title}</b>
              <span>{task.end_date}</span>
              <span>{task.progress}%</span>
            </div>
          ))}
        </div>
      </article>
    </section>
  );
}
