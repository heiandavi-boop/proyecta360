import { LogOut } from "lucide-react";

import type { PublicUser } from "@/api/client";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { APP_VIEWS, type AppView } from "@/domain/views";
import { useI18n } from "@/i18n/i18n";

type TopBarProps = {
  activeView: AppView;
  user: PublicUser | null;
  onViewChange: (view: AppView) => void;
  onLogout: () => void;
};

export function TopBar({ activeView, user, onViewChange, onLogout }: TopBarProps) {
  const { t } = useI18n();

  return (
    <>
      <aside className="sidebar">
        <strong className="brand">PRUNIN</strong>
        <nav className="main-tabs" aria-label="Main navigation">
          {APP_VIEWS.map((item) => {
            const Icon = item.icon;
            return (
              <button
                className={activeView === item.id ? "active" : ""}
                key={item.id}
                onClick={() => onViewChange(item.id)}
                type="button"
              >
                <Icon size={17} />
                <span>{t(item.labelKey)}</span>
              </button>
            );
          })}
        </nav>
      </aside>
      <header className="topbar">
        <div className="topbar-title">
          <strong>{t(`view.${activeView}`)}</strong>
          <span>{t("brand.subtitle")}</span>
        </div>
        <LanguageSwitcher />
        <div className="user-chip">
          <span className="sync-dot" />
          <span>{user ? `${user.name} - ${user.role}` : t("auth.noSession")}</span>
          {user ? (
            <button className="icon-button" onClick={onLogout} title={t("auth.logout")} type="button">
              <LogOut size={17} />
            </button>
          ) : null}
        </div>
      </header>
    </>
  );
}
