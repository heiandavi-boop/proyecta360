import { useMemo, useState, type FormEvent } from "react";

import type { RiskIn } from "@contracts/types";

import type { BootstrapPayload } from "@/domain/project";
import { useI18n } from "@/i18n/i18n";

type RisksViewProps = {
  data: BootstrapPayload;
  busy?: boolean;
  canWrite?: boolean;
  onCreateRisk: (risk: RiskIn) => Promise<void>;
};

function levelClass(level: string) {
  const normalized = level.toLowerCase();
  if (normalized.includes("crit") || normalized.includes("alto")) return "badge danger";
  if (normalized.includes("medio")) return "badge warning";
  return "badge success";
}

function uniquePeople(values: Array<string | null | undefined>) {
  return Array.from(new Set(values.map((value) => String(value || "").trim()).filter(Boolean))).sort((left, right) => left.localeCompare(right));
}

export function RisksView({ busy = false, canWrite = true, data, onCreateRisk }: RisksViewProps) {
  const { t } = useI18n();
  const ownerOptions = useMemo(() => uniquePeople([
    data.current_project.project_manager,
    ...data.resources.map((resource) => resource.name),
    ...data.tasks.map((task) => task.owner),
    ...data.risks.map((risk) => risk.owner),
    ...data.components.map((component) => component.owner),
    ...data.deliverables.map((deliverable) => deliverable.owner),
    ...data.stories.map((story) => story.assignee),
  ]), [data.components, data.current_project.project_manager, data.deliverables, data.resources, data.risks, data.stories, data.tasks]);
  const [showForm, setShowForm] = useState(false);
  const [draft, setDraft] = useState<RiskIn>({
    project_id: data.current_project.id,
    title: "",
    probability: 3,
    impact: 3,
    response: "Mitigar",
    mitigation_plan: "",
    contingency_plan: "",
    status: "Abierto",
    owner: "",
  });

  async function submitRisk(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onCreateRisk({ ...draft, project_id: data.current_project.id });
    setShowForm(false);
    setDraft((current) => ({ ...current, title: "", mitigation_plan: "", contingency_plan: "" }));
  }

  return (
    <section className="section-stack">
      <div className="page-toolbar">
        <div>
          <h2>{t("risks.title")}</h2>
          <span>{data.metrics.high_risks} {t("common.high")}</span>
        </div>
        {canWrite ? <button className="primary-action compact-action" disabled={busy} onClick={() => setShowForm((value) => !value)} type="button">{t("risks.add")}</button> : null}
      </div>
      {canWrite && showForm ? (
        <form className="inline-form panel" onSubmit={(event) => void submitRisk(event)}>
          <label className="wide-field">{t("risks.risk")}<input required value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label>
          <label>{t("risk.probability15")}<input max="5" min="1" type="number" value={draft.probability || 1} onChange={(event) => setDraft({ ...draft, probability: Number(event.target.value) })} /></label>
          <label>{t("risk.impact15")}<input max="5" min="1" type="number" value={draft.impact || 1} onChange={(event) => setDraft({ ...draft, impact: Number(event.target.value) })} /></label>
          <label>{t("common.owner")}<select value={draft.owner || ""} onChange={(event) => setDraft({ ...draft, owner: event.target.value })}><option value="">{t("knowledge.noOwner")}</option>{ownerOptions.map((owner) => <option key={owner} value={owner}>{owner}</option>)}</select></label>
          <label>{t("risk.mitigationPlan")}<input value={draft.mitigation_plan || ""} onChange={(event) => setDraft({ ...draft, mitigation_plan: event.target.value })} /></label>
          <label>{t("risk.contingencyPlan")}<input value={draft.contingency_plan || ""} onChange={(event) => setDraft({ ...draft, contingency_plan: event.target.value })} /></label>
          <div className="form-actions"><button className="icon-button" onClick={() => setShowForm(false)} type="button">{t("common.cancel")}</button><button className="primary-action" disabled={busy} type="submit">{busy ? t("common.saving") : t("common.create")}</button></div>
        </form>
      ) : null}
      <div className="panel">
        <div className="table-scroll">
          <table className="data-table">
            <thead><tr><th>{t("risks.risk")}</th><th>{t("risks.level")}</th><th>{t("risks.probability")}</th><th>{t("risks.impact")}</th><th>{t("risk.strategy")}</th><th>{t("risks.mitigation")}</th><th>{t("risks.contingency")}</th><th>{t("common.owner")}</th><th>{t("common.status")}</th></tr></thead>
            <tbody>
              {data.risks.map((risk) => (
                <tr key={risk.id}>
                  <td><strong>{risk.title}</strong></td>
                  <td><span className={levelClass(risk.level)}>{risk.level}</span></td>
                  <td>{risk.probability}</td>
                  <td>{risk.impact}</td>
                  <td>{risk.response || "-"}</td>
                  <td>{risk.mitigation_plan || "-"}</td>
                  <td>{risk.contingency_plan || "-"}</td>
                  <td>{risk.owner || t("knowledge.noOwner")}</td>
                  <td><span className="badge neutral">{risk.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
