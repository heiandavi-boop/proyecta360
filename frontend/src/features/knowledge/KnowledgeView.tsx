import { useMemo, useState, type FormEvent } from "react";

import type { ComponentIn, DeliverableIn } from "@contracts/types";

import type { BootstrapPayload } from "@/domain/project";
import { useI18n } from "@/i18n/i18n";

type KnowledgeViewProps = {
  data: BootstrapPayload;
  busy?: boolean;
  canWrite?: boolean;
  onCreateComponent: (component: ComponentIn) => Promise<void>;
  onCreateDeliverable: (deliverable: DeliverableIn) => Promise<void>;
  onUploadEvidence: (formData: FormData, projectId: number) => Promise<void>;
};

function uniquePeople(values: Array<string | null | undefined>) {
  return Array.from(new Set(values.map((value) => String(value || "").trim()).filter(Boolean))).sort((left, right) => left.localeCompare(right));
}

export function KnowledgeView({ busy = false, canWrite = true, data, onCreateComponent, onCreateDeliverable, onUploadEvidence }: KnowledgeViewProps) {
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
  const [form, setForm] = useState<"component" | "deliverable" | "evidence" | "">("");
  const [componentDraft, setComponentDraft] = useState<ComponentIn>({
    project_id: data.current_project.id,
    name: "",
    methodology: "Hibrida",
    owner: "",
    objective: "",
    progress: 0,
  });
  const [deliverableDraft, setDeliverableDraft] = useState<DeliverableIn>({
    project_id: data.current_project.id,
    name: "",
    deliverable_type: "Entregable",
    status: "Planeado",
    owner: "",
    description: "",
    evidence_url: "",
  });
  const [evidenceDraft, setEvidenceDraft] = useState({
    entity_type: "Proyecto",
    entity_id: "",
    uploaded_by: data.current_user?.name || "Equipo",
    description: "",
    file: null as File | null,
  });

  async function submitComponent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onCreateComponent({ ...componentDraft, project_id: data.current_project.id });
    setForm("");
    setComponentDraft((current) => ({ ...current, name: "", objective: "" }));
  }

  async function submitDeliverable(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onCreateDeliverable({ ...deliverableDraft, project_id: data.current_project.id });
    setForm("");
    setDeliverableDraft((current) => ({ ...current, name: "", description: "", evidence_url: "" }));
  }

  async function submitEvidence(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!evidenceDraft.file) return;
    const body = new FormData();
    body.set("project_id", String(data.current_project.id));
    body.set("entity_type", evidenceDraft.entity_type);
    if (evidenceDraft.entity_id) body.set("entity_id", evidenceDraft.entity_id);
    body.set("uploaded_by", evidenceDraft.uploaded_by);
    body.set("description", evidenceDraft.description);
    body.set("file", evidenceDraft.file);
    await onUploadEvidence(body, data.current_project.id);
    setForm("");
    setEvidenceDraft((current) => ({ ...current, description: "", file: null }));
  }

  return (
    <section className="dashboard-grid">
      <article className="panel">
        <div className="panel-heading">
          <div>
            <h2>{t("knowledge.componentsTitle")}</h2>
            <span>{t("knowledge.componentsDescription")}</span>
          </div>
          {canWrite ? <button className="primary-action compact-action" disabled={busy} onClick={() => setForm("component")} type="button">{t("knowledge.addComponent")}</button> : null}
        </div>
        {canWrite && form === "component" ? (
          <form className="stack-form" onSubmit={(event) => void submitComponent(event)}>
            <label>{t("common.name")}<input required value={componentDraft.name} onChange={(event) => setComponentDraft({ ...componentDraft, name: event.target.value })} /></label>
            <label>{t("component.methodology")}<select value={componentDraft.methodology} onChange={(event) => setComponentDraft({ ...componentDraft, methodology: event.target.value })}><option>Tradicional</option><option>Scrum</option><option>Kanban</option><option>Hibrida</option></select></label>
            <label>{t("common.owner")}<select value={componentDraft.owner || ""} onChange={(event) => setComponentDraft({ ...componentDraft, owner: event.target.value })}><option value="">{t("knowledge.noOwner")}</option>{ownerOptions.map((owner) => <option key={owner} value={owner}>{owner}</option>)}</select></label>
            <label>{t("gantt.progress")}<input max="100" min="0" type="number" value={componentDraft.progress || 0} onChange={(event) => setComponentDraft({ ...componentDraft, progress: Number(event.target.value) })} /></label>
            <label>{t("component.objective")}<textarea rows={3} value={componentDraft.objective || ""} onChange={(event) => setComponentDraft({ ...componentDraft, objective: event.target.value })} /></label>
            <div className="form-actions"><button className="icon-button" onClick={() => setForm("")} type="button">{t("common.cancel")}</button><button className="primary-action" disabled={busy} type="submit">{t("common.create")}</button></div>
          </form>
        ) : null}
        {data.components.map((component) => (
          <div className="component-row" key={component.id}>
            <b>{component.name}</b>
            <span>{component.methodology}</span>
            <small>{component.progress}%</small>
          </div>
        ))}
      </article>
      <article className="panel">
        <div className="panel-heading">
          <div>
            <h2>{t("knowledge.productsTitle")}</h2>
            <span>{t("knowledge.productsDescription")}</span>
          </div>
          {canWrite ? <button className="primary-action compact-action" disabled={busy} onClick={() => setForm("deliverable")} type="button">{t("knowledge.addProduct")}</button> : null}
        </div>
        {canWrite && form === "deliverable" ? (
          <form className="stack-form" onSubmit={(event) => void submitDeliverable(event)}>
            <label>{t("common.name")}<input required value={deliverableDraft.name} onChange={(event) => setDeliverableDraft({ ...deliverableDraft, name: event.target.value })} /></label>
            <label>{t("knowledge.component")}<select value={deliverableDraft.component_id || ""} onChange={(event) => setDeliverableDraft({ ...deliverableDraft, component_id: event.target.value ? Number(event.target.value) : null })}><option value="">{t("knowledge.noComponent")}</option>{data.components.map((component) => <option key={component.id} value={component.id}>{component.name}</option>)}</select></label>
            <label>{t("deliverable.type")}<select value={deliverableDraft.deliverable_type} onChange={(event) => setDeliverableDraft({ ...deliverableDraft, deliverable_type: event.target.value })}><option>Entregable</option><option>Producto de conocimiento</option><option>Evidencia</option><option>Informe</option></select></label>
            <label>{t("common.status")}<input value={deliverableDraft.status || ""} onChange={(event) => setDeliverableDraft({ ...deliverableDraft, status: event.target.value })} /></label>
            <label>{t("deliverable.dueDate")}<input type="date" value={deliverableDraft.due_date || ""} onChange={(event) => setDeliverableDraft({ ...deliverableDraft, due_date: event.target.value || null })} /></label>
            <label>{t("deliverable.evidenceUrl")}<input value={deliverableDraft.evidence_url || ""} onChange={(event) => setDeliverableDraft({ ...deliverableDraft, evidence_url: event.target.value })} /></label>
            <div className="form-actions"><button className="icon-button" onClick={() => setForm("")} type="button">{t("common.cancel")}</button><button className="primary-action" disabled={busy} type="submit">{t("common.create")}</button></div>
          </form>
        ) : null}
        {data.deliverables.map((deliverable) => (
          <div className="component-row" key={deliverable.id}>
            <b>{deliverable.name}</b>
            <span>{deliverable.status}</span>
            <small>{deliverable.due_date || "-"}</small>
          </div>
        ))}
      </article>
      <article className="panel full-span">
        <div className="panel-heading">
          <div>
            <h2>{t("knowledge.loadedEvidenceTitle")}</h2>
            <span>{t("knowledge.loadedEvidenceDescription")}</span>
          </div>
          {canWrite ? <button className="primary-action compact-action" disabled={busy} onClick={() => setForm("evidence")} type="button">{t("knowledge.addEvidence")}</button> : null}
        </div>
        {canWrite && form === "evidence" ? (
          <form className="inline-form" onSubmit={(event) => void submitEvidence(event)}>
            <label>{t("knowledge.associatedTo")}<select value={evidenceDraft.entity_type} onChange={(event) => setEvidenceDraft({ ...evidenceDraft, entity_type: event.target.value, entity_id: "" })}><option>Proyecto</option><option>Tarea</option><option>Entregable</option><option>Riesgo</option><option>Componente</option></select></label>
            <label>{t("common.file")}<input required type="file" onChange={(event) => setEvidenceDraft({ ...evidenceDraft, file: event.target.files?.[0] || null })} /></label>
            <label className="wide-field">{t("common.description")}<input value={evidenceDraft.description} onChange={(event) => setEvidenceDraft({ ...evidenceDraft, description: event.target.value })} /></label>
            <div className="form-actions"><button className="icon-button" onClick={() => setForm("")} type="button">{t("common.cancel")}</button><button className="primary-action" disabled={busy} type="submit">{t("evidence.attach")}</button></div>
          </form>
        ) : null}
        <div className="data-grid evidence-grid">
          <b>{t("common.file")}</b><b>{t("knowledge.associatedTo")}</b><b>{t("knowledge.uploadedBy")}</b><b>{t("knowledge.size")}</b><b>{t("knowledge.download")}</b>
          {data.evidences.map((evidence) => (
            <div className="data-row evidence-grid" key={evidence.id}>
              <span>{evidence.original_filename}</span>
              <span>{evidence.entity_type} {evidence.entity_id || ""}</span>
              <span>{evidence.uploaded_by || t("common.system")}</span>
              <span>{Number(evidence.size_bytes || 0).toLocaleString()}</span>
              <span><a href={evidence.download_url} rel="noreferrer" target="_blank">{t("knowledge.download")}</a></span>
            </div>
          ))}
        </div>
      </article>
    </section>
  );
}
