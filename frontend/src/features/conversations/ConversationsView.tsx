import { useMemo, useState, type FormEvent } from "react";

import type { ConversationMessageIn, ConversationThreadIn } from "@contracts/types";

import type { BootstrapPayload } from "@/domain/project";
import { useI18n } from "@/i18n/i18n";

type ConversationsViewProps = {
  data: BootstrapPayload;
  busy?: boolean;
  canWrite?: boolean;
  onCreateMessage: (threadId: number, message: ConversationMessageIn) => Promise<void>;
  onCreateThread: (thread: ConversationThreadIn) => Promise<void>;
};

export function ConversationsView({ busy = false, canWrite = true, data, onCreateMessage, onCreateThread }: ConversationsViewProps) {
  const { t } = useI18n();
  const [activeThreadId, setActiveThreadId] = useState(data.conversation_threads[0]?.id || 0);
  const [showThreadForm, setShowThreadForm] = useState(false);
  const [threadDraft, setThreadDraft] = useState<ConversationThreadIn>({
    project_id: data.current_project.id,
    title: "",
    context_type: "Proyecto",
    category: "Seguimiento",
    status: "Abierta",
    created_by: data.current_user?.name || "Equipo",
  });
  const [messageDraft, setMessageDraft] = useState({
    author: data.current_user?.name || "Equipo",
    message: "",
    message_type: "Comentario",
    mentions: "",
    evidence_url: "",
  });

  const activeThread = data.conversation_threads.find((thread) => thread.id === activeThreadId) || data.conversation_threads[0];
  const messages = useMemo(
    () => data.conversation_messages.filter((message) => message.thread_id === activeThread?.id),
    [activeThread?.id, data.conversation_messages]
  );

  async function submitThread(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onCreateThread({ ...threadDraft, project_id: data.current_project.id });
    setShowThreadForm(false);
    setThreadDraft((current) => ({ ...current, title: "" }));
  }

  async function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeThread) return;
    await onCreateMessage(activeThread.id, {
      ...messageDraft,
      project_id: data.current_project.id,
      thread_id: activeThread.id,
    });
    setMessageDraft((current) => ({ ...current, message: "", mentions: "", evidence_url: "" }));
  }

  return (
    <section className="dashboard-grid">
      <aside className="panel">
        <div className="panel-heading">
          <div>
            <h2>{t("conversation.title")}</h2>
            <span>{data.conversation_threads.length} {t("common.messages")}</span>
          </div>
          {canWrite ? (
            <button className="primary-action compact-action" disabled={busy} onClick={() => setShowThreadForm((value) => !value)} type="button">
              {t("conversation.newThread")}
            </button>
          ) : null}
        </div>
        {canWrite && showThreadForm ? (
          <form className="stack-form" onSubmit={(event) => void submitThread(event)}>
            <label>{t("story.title")}<input required value={threadDraft.title} onChange={(event) => setThreadDraft({ ...threadDraft, title: event.target.value })} /></label>
            <label>{t("conversation.type")}<select value={threadDraft.category} onChange={(event) => setThreadDraft({ ...threadDraft, category: event.target.value })}><option>Seguimiento</option><option>Acuerdo</option><option>Bloqueo</option><option>Decision</option></select></label>
            <div className="form-actions">
              <button className="icon-button" onClick={() => setShowThreadForm(false)} type="button">{t("common.cancel")}</button>
              <button className="primary-action" disabled={busy} type="submit">{t("common.create")}</button>
            </div>
          </form>
        ) : null}
        <div className="thread-list">
          {data.conversation_threads.map((thread) => (
            <button className={`thread-item ${thread.id === activeThread?.id ? "active-thread" : ""}`} key={thread.id} onClick={() => setActiveThreadId(thread.id)} type="button">
              <b>{thread.title}</b>
              <span>{thread.context_type} - {thread.category}</span>
              <small>{thread.status}</small>
            </button>
          ))}
        </div>
      </aside>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>{activeThread?.title || t("conversation.select")}</h2>
            <span>{messages.length} {t("common.messages")}</span>
          </div>
        </div>
        <div className="message-list">
          {messages.map((message) => (
            <article className="message-item" key={message.id}>
              <b>{message.author || t("common.team")}</b>
              <p>{message.message}</p>
              <small>{message.message_type} {message.created_at || ""}</small>
            </article>
          ))}
          {!messages.length ? <p>{t("common.noMessagesYet")}</p> : null}
        </div>
        {canWrite && activeThread ? (
          <form className="stack-form" onSubmit={(event) => void submitMessage(event)}>
            <label>{t("conversation.author")}<input value={messageDraft.author} onChange={(event) => setMessageDraft({ ...messageDraft, author: event.target.value })} /></label>
            <label>{t("conversation.type")}<select value={messageDraft.message_type} onChange={(event) => setMessageDraft({ ...messageDraft, message_type: event.target.value })}><option>Comentario</option><option>Acuerdo</option><option>Decision</option><option>Bloqueo</option></select></label>
            <label>{t("conversation.message")}<textarea required rows={4} value={messageDraft.message} onChange={(event) => setMessageDraft({ ...messageDraft, message: event.target.value })} /></label>
            <div className="form-actions">
              <button className="primary-action" disabled={busy} type="submit">{busy ? t("common.saving") : t("conversation.send")}</button>
            </div>
          </form>
        ) : null}
      </section>
    </section>
  );
}
