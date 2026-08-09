import {
  AlertTriangle,
  Bot,
  BriefcaseBusiness,
  CalendarRange,
  CircleDollarSign,
  KanbanSquare,
  Library,
  MessagesSquare,
  Users
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export type AppView =
  | "portfolio"
  | "master-plan"
  | "scrum"
  | "resources"
  | "budget"
  | "risks"
  | "conversations"
  | "knowledge"
  | "ai";

export const APP_VIEWS = [
  { id: "portfolio", labelKey: "top.portfolio", icon: BriefcaseBusiness },
  { id: "master-plan", labelKey: "top.masterPlan", icon: CalendarRange },
  { id: "scrum", labelKey: "nav.scrum", icon: KanbanSquare },
  { id: "resources", labelKey: "nav.resources", icon: Users },
  { id: "budget", labelKey: "nav.budget", icon: CircleDollarSign },
  { id: "risks", labelKey: "nav.risks", icon: AlertTriangle },
  { id: "conversations", labelKey: "nav.conversations", icon: MessagesSquare },
  { id: "knowledge", labelKey: "nav.knowledge", icon: Library },
  { id: "ai", labelKey: "nav.ai", icon: Bot }
] as const satisfies ReadonlyArray<{
  id: AppView;
  labelKey: string;
  icon: LucideIcon;
}>;
