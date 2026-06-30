"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard, Building2, Users, MessageSquare,
  FileText, Send, BarChart3, Puzzle, Settings, UserCog,
} from "lucide-react";

const navItems = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Clinics", href: "/clinics", icon: Building2 },
  { label: "CRM", href: "/crm", icon: Users },
  { label: "AI Dialogs", href: "/dialogs", icon: MessageSquare },
  { label: "Content Studio", href: "/content", icon: FileText },
  { label: "Publishing", href: "/publishing", icon: Send },
  { label: "Reports", href: "/reports", icon: BarChart3 },
  { label: "Integrations", href: "/integrations", icon: Puzzle },
  { label: "Users", href: "/users", icon: UserCog },
  { label: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-60 flex-col border-r bg-sidebar">
      <div className="flex h-14 items-center gap-2 border-b px-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">AO</div>
        <span className="text-base font-semibold text-sidebar-foreground">Agency OS</span>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {navItems.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active ? "bg-sidebar-active text-primary" : "text-sidebar-foreground hover:bg-sidebar-muted hover:text-sidebar-foreground",
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
