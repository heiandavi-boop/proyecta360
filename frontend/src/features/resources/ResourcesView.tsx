import { useState, type FormEvent } from "react";

import type { ResourceIn } from "@contracts/types";

import type { BootstrapPayload } from "@/domain/project";
import { useI18n } from "@/i18n/i18n";

type ResourcesViewProps = {
  data: BootstrapPayload;
  busy?: boolean;
  canWrite?: boolean;
  onCreateResource: (resource: ResourceIn) => Promise<void>;
};

export function ResourcesView({ busy = false, canWrite = true, data, onCreateResource }: ResourcesViewProps) {
  const { t } = useI18n();
  const [showForm, setShowForm] = useState(false);
  const [draft, setDraft] = useState<ResourceIn>({
    project_id: data.current_project.id,
    name: "",
    role: "",
    email: "",
    capacity: 100,
  });

  async function submitResource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onCreateResource({ ...draft, project_id: data.current_project.id });
    setShowForm(false);
    setDraft((current) => ({ ...current, name: "", role: "", email: "", capacity: 100 }));
  }

  return (
    <section className="section-stack">
      <div className="page-toolbar">
        <div><h2>{t("resources.title")}</h2><span>{t("resources.description")}</span></div>
        {canWrite ? <button className="primary-action compact-action" disabled={busy} onClick={() => setShowForm((value) => !value)} type="button">{t("resources.add")}</button> : null}
      </div>
      {canWrite && showForm ? (
        <form className="inline-form panel" onSubmit={(event) => void submitResource(event)}>
          <label>{t("common.name")}<input required value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
          <label>{t("common.role")}<input value={draft.role || ""} onChange={(event) => setDraft({ ...draft, role: event.target.value })} /></label>
          <label>{t("common.email")}<input type="email" value={draft.email || ""} onChange={(event) => setDraft({ ...draft, email: event.target.value })} /></label>
          <label>{t("resources.capacity")}<input max="100" min="0" type="number" value={draft.capacity || 0} onChange={(event) => setDraft({ ...draft, capacity: Number(event.target.value) })} /></label>
          <div className="form-actions"><button className="icon-button" onClick={() => setShowForm(false)} type="button">{t("common.cancel")}</button><button className="primary-action" disabled={busy} type="submit">{busy ? t("common.saving") : t("common.create")}</button></div>
        </form>
      ) : null}
      <div className="panel">
        <div className="table-scroll">
          <table className="data-table">
            <thead><tr><th>{t("common.name")}</th><th>{t("common.role")}</th><th>{t("common.email")}</th><th>{t("resources.capacity")}</th><th>{t("common.status")}</th></tr></thead>
            <tbody>
              {data.resources.map((resource) => (
                <tr key={resource.id}>
                  <td><strong>{resource.name}</strong></td>
                  <td>{resource.role || t("common.rolePending")}</td>
                  <td>{resource.email || "-"}</td>
                  <td><div className="progress-cell capacity"><i style={{ width: `${resource.capacity}%` }} /><span>{resource.capacity}%</span></div></td>
                  <td><span className={resource.capacity > 100 ? "badge danger" : resource.capacity >= 90 ? "badge warning" : "badge success"}>{resource.capacity > 100 ? "Sobrecarga" : "Disponible"}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
