import type { ReactNode } from "react";
import { FileDown } from "lucide-react";

import type { BootstrapPayload } from "@/domain/project";
import type { AppView } from "@/domain/views";
import { useI18n } from "@/i18n/i18n";

type ProjectShellProps = {
  activeView: AppView;
  data: BootstrapPayload;
  children: ReactNode;
  loading?: boolean;
  reportBusy?: boolean;
  onDownloadReport?: () => void;
  onProjectChange?: (projectId: number) => void;
};

export function ProjectShell({ activeView, data, children, reportBusy = false, onDownloadReport }: ProjectShellProps) {
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
          {onDownloadReport ? (
            <button className="report-action" disabled={reportBusy} onClick={onDownloadReport} type="button">
              <FileDown size={16} />
              <span>{reportBusy ? "Generando PDF..." : "Generar informe PDF"}</span>
            </button>
          ) : null}
          <span className="view-pill">{t(`view.${activeView}`)}</span>
        </div>
      </section>
      {children}
    </main>
  );
}
