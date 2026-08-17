"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { BarChart3, BookOpen, Boxes, BrainCircuit, FileText, Layers3, LayoutDashboard, Send, Settings, UserCog } from "lucide-react";

const navItems = [
  { label: "Factory", href: "/dashboard", icon: LayoutDashboard },
  { label: "Batches", href: "/batches", icon: Boxes },
  { label: "Brand Brain", href: "/brand", icon: BrainCircuit },
  { label: "Knowledge Base", href: "/knowledge", icon: BookOpen },
  { label: "Strategy & Rubrics", href: "/rubrics", icon: Layers3 },
  { label: "Content", href: "/content", icon: FileText },
  { label: "Autoposter Outbox", href: "/publishing", icon: Send },
  { label: "Performance", href: "/performance", icon: BarChart3 },
  { label: "Users", href: "/users", icon: UserCog },
  { label: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-60 flex-col border-r bg-sidebar">
      <div className="flex h-14 items-center gap-2 border-b px-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">CF</div>
        <div>
          <span className="block text-base font-semibold text-sidebar-foreground">Content Factory</span>
          <span className="block text-[10px] uppercase tracking-[0.18em] text-muted-foreground">AI production OS</span>
        </div>
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
