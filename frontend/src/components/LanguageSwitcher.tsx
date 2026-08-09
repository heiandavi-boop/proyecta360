import { useI18n } from "@/i18n/i18n";

export function LanguageSwitcher() {
  const { language, languages, setLanguage } = useI18n();

  return (
    <div className="language-switcher" aria-label="Language selector">
      {languages.map((item) => (
        <button
          className={`language-option ${language === item.code ? "active" : ""}`}
          key={item.code}
          onClick={() => void setLanguage(item.code)}
          title={item.native}
          type="button"
        >
          <span className={`language-flag flag-${item.code}`} />
        </button>
      ))}
    </div>
  );
}
