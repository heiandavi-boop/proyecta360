import { useMemo, useState, type FormEvent } from "react";

import type { BudgetEntryIn } from "@contracts/types";

import type { BootstrapPayload, BudgetEntry } from "@/domain/project";

type BudgetViewProps = {
  data: BootstrapPayload;
  busy?: boolean;
  canWrite?: boolean;
  onCreateBudgetEntry: (entry: BudgetEntryIn) => Promise<void>;
  onDeleteBudgetEntry: (entryId: number) => Promise<void>;
};

function currentMonth() {
  return new Date().toISOString().slice(0, 7);
}

function money(value: unknown, currency: string) {
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(Number(value || 0))} ${currency}`;
}

function varianceClass(value: number) {
  if (value > 0) return "signal danger";
  if (value < 0) return "signal warning";
  return "signal success";
}

function byCategory(entries: BudgetEntry[]) {
  return Object.values(entries.reduce<Record<string, { category: string; planned: number; executed: number }>>((acc, entry) => {
    const key = entry.category || "General";
    acc[key] ||= { category: key, planned: 0, executed: 0 };
    acc[key].planned += Number(entry.planned_amount || 0);
    acc[key].executed += Number(entry.executed_amount || 0);
    return acc;
  }, {})).sort((left, right) => left.category.localeCompare(right.category));
}

export function BudgetView({ busy = false, canWrite = true, data, onCreateBudgetEntry, onDeleteBudgetEntry }: BudgetViewProps) {
  const currency = data.current_project.currency;
  const entries = data.budget_entries || [];
  const [showForm, setShowForm] = useState(false);
  const [draft, setDraft] = useState<BudgetEntryIn>({
    project_id: data.current_project.id,
    month: currentMonth(),
    category: "General",
    planned_amount: 0,
    executed_amount: 0,
    notes: "",
  });
  const totals = useMemo(() => ({
    planned: entries.reduce((sum, entry) => sum + Number(entry.planned_amount || 0), 0),
    executed: entries.reduce((sum, entry) => sum + Number(entry.executed_amount || 0), 0),
    categories: byCategory(entries),
  }), [entries]);
  const variance = totals.executed - totals.planned;

  async function submitEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onCreateBudgetEntry({ ...draft, project_id: data.current_project.id });
    setShowForm(false);
    setDraft((current) => ({ ...current, planned_amount: 0, executed_amount: 0, notes: "" }));
  }

  return (
    <section className="section-stack">
      <div className="page-toolbar">
        <div>
          <h2>Presupuesto</h2>
          <span>Plan de ejecucion mensual por rubro y seguimiento acumulado.</span>
        </div>
        {canWrite ? <button className="primary-action compact-action" disabled={busy} onClick={() => setShowForm((value) => !value)} type="button">+ Registro</button> : null}
      </div>

      <section className="budget-summary-grid">
        <article className="panel budget-summary-card"><span>Planificado total</span><strong>{money(totals.planned, currency)}</strong></article>
        <article className="panel budget-summary-card"><span>Ejecutado total</span><strong>{money(totals.executed, currency)}</strong></article>
        <article className="panel budget-summary-card"><span>Desviacion</span><strong className={varianceClass(variance)}>{money(variance, currency)}</strong></article>
        <article className="panel budget-summary-card"><span>Fuente PHS</span><strong>{data.metrics.budget_source === "plan_mensual" ? "Plan mensual" : "Estimado por tareas"}</strong></article>
      </section>

      {canWrite && showForm ? (
        <form className="inline-form panel" onSubmit={(event) => void submitEntry(event)}>
          <label>Mes<input required type="month" value={draft.month} onChange={(event) => setDraft({ ...draft, month: event.target.value })} /></label>
          <label>Rubro<input required value={draft.category} onChange={(event) => setDraft({ ...draft, category: event.target.value })} /></label>
          <label>Planificado<input min="0" type="number" value={draft.planned_amount || 0} onChange={(event) => setDraft({ ...draft, planned_amount: Number(event.target.value) })} /></label>
          <label>Ejecutado<input min="0" type="number" value={draft.executed_amount || 0} onChange={(event) => setDraft({ ...draft, executed_amount: Number(event.target.value) })} /></label>
          <label className="wide-field">Notas<input value={draft.notes || ""} onChange={(event) => setDraft({ ...draft, notes: event.target.value })} /></label>
          <div className="form-actions"><button className="icon-button" onClick={() => setShowForm(false)} type="button">Cancelar</button><button className="primary-action" disabled={busy} type="submit">{busy ? "Guardando..." : "Guardar registro"}</button></div>
        </form>
      ) : null}

      <section className="dashboard-grid">
        <article className="panel">
          <div className="panel-heading">
            <div><h2>Resumen por rubro</h2><span>{totals.categories.length} rubros registrados</span></div>
          </div>
          <div className="table-scroll">
            <table className="data-table">
              <thead><tr><th>Rubro</th><th>Planificado</th><th>Ejecutado</th><th>Desviacion</th></tr></thead>
              <tbody>
                {totals.categories.map((row) => (
                  <tr key={row.category}>
                    <td><strong>{row.category}</strong></td>
                    <td>{money(row.planned, currency)}</td>
                    <td>{money(row.executed, currency)}</td>
                    <td><span className={varianceClass(row.executed - row.planned)}>{money(row.executed - row.planned, currency)}</span></td>
                  </tr>
                ))}
                {!totals.categories.length ? <tr><td colSpan={4}>Sin presupuesto mensual registrado.</td></tr> : null}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel">
          <div className="panel-heading">
            <div><h2>Registros mensuales</h2><span>Planificado vs ejecutado por mes y rubro</span></div>
          </div>
          <div className="table-scroll">
            <table className="data-table">
              <thead><tr><th>Mes</th><th>Rubro</th><th>Planificado</th><th>Ejecutado</th><th>Notas</th><th></th></tr></thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.id}>
                    <td>{entry.month}</td>
                    <td><strong>{entry.category}</strong></td>
                    <td>{money(entry.planned_amount, currency)}</td>
                    <td>{money(entry.executed_amount, currency)}</td>
                    <td>{entry.notes || "-"}</td>
                    <td>{canWrite ? <button className="inline-action" disabled={busy} onClick={() => void onDeleteBudgetEntry(entry.id)} type="button">Eliminar</button> : null}</td>
                  </tr>
                ))}
                {!entries.length ? <tr><td colSpan={6}>Agrega el primer mes para que el PHS use presupuesto real.</td></tr> : null}
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </section>
  );
}
