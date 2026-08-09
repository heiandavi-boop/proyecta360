import type { ReactNode } from "react";

import type { BootstrapPayload } from "@/domain/project";
import type { AppView } from "@/domain/views";
import { useI18n } from "@/i18n/i18n";

type ProjectShellProps = {
  activeView: AppView;
  data: BootstrapPayload;
  children: ReactNode;
  loading?: boolean;
  onProjectChange: (projectId: number) => void;
};

export function ProjectShell({ activeView, data, children, loading = false, onProjectChange }: ProjectShellProps) {
  const { t } = useI18n();
  const project = data.current_project;

  return (
    <main className="workspace">
      <section className="project-heading">
        <div>
          <h1>{project.name}</h1>
          <p>{project.description || t("project.noDescription")}</p>
        </div>
        <div className="project-controls">
          <select
            aria-label={t("project.label")}
            disabled={loading}
            onChange={(event) => onProjectChange(Number(event.target.value))}
            value={project.id}
          >
            {data.projects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <span className="view-pill">{t(`view.${activeView}`)}</span>
        </div>
      </section>
      {children}
    </main>
  );
}
