import { FormEvent, useState } from "react";

import { login, saveToken } from "@/api/client";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useI18n } from "@/i18n/i18n";

type LoginViewProps = {
  onAuthenticated: () => void;
};

export function LoginView({ onAuthenticated }: LoginViewProps) {
  const { t } = useI18n();
  const [email, setEmail] = useState("admin@proyecta360.local");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const response = await login({ email, password });
      saveToken(response.token);
      onAuthenticated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-shell">
      <LanguageSwitcher />
      <section>
        <p className="eyebrow">Proyecta360</p>
        <h1>{t("auth.hero.title")}</h1>
        <p>{t("auth.hero.description")}</p>
      </section>
      <form className="login-panel" onSubmit={submit}>
        <h2>{t("auth.login.title")}</h2>
        <label>
          <span>{t("auth.email")}</span>
          <input autoComplete="username" onChange={(event) => setEmail(event.target.value)} type="email" value={email} />
        </label>
        <label>
          <span>{t("auth.password")}</span>
          <input autoComplete="current-password" onChange={(event) => setPassword(event.target.value)} type="password" value={password} />
        </label>
        {error ? <p className="error-text">{error}</p> : null}
        <button className="primary-action" disabled={loading} type="submit">
          {loading ? t("ai.analyzing") : t("auth.submit")}
        </button>
      </form>
    </main>
  );
}
