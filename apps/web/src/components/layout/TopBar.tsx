"use client";

import { useAuth } from "@/context/AuthContext";
import { useProject } from "@/context/ProjectContext";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { LogOut, HelpCircle, CheckCircle, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const mockIntegrationStatuses = [
  { name: "CRM", status: "healthy" },
  { name: "AI", status: "healthy" },
  { name: "Content", status: "degraded" },
  { name: "Auto", status: "healthy" },
  { name: "Reports", status: "healthy" },
] as const;

export function TopBar() {
  const { user, logout } = useAuth();
  const { current, setCurrent } = useProject();
  const [projectList, setProjectList] = useState<{ id: string; name: string }[]>([]);

  useEffect(() => {
    api.get<{ id: string; name: string }[]>("/projects").then(setProjectList).catch(() => {});
  }, []);

  const initials = user?.name?.split(" ").map((n) => n[0]).join("").toUpperCase().slice(0, 2) ?? "U";

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-background px-6">
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-muted-foreground">Project:</span>
        <select
          className="rounded-md border bg-background px-3 py-1.5 text-sm"
          value={current?.id ?? ""}
          onChange={(e) => {
            const p = projectList.find((p) => p.id === e.target.value);
            if (p) setCurrent(p);
          }}
        >
          <option value="">Select project</option>
          {projectList.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
      </div>

      <div className="flex items-center gap-4">
        <div className="hidden items-center gap-2 md:flex">
          {mockIntegrationStatuses.map((s) => (
            <Badge
              key={s.name}
              variant={s.status === "healthy" ? "success" : s.status === "degraded" ? "warning" : "destructive"}
              className="gap-1"
            >
              {s.status === "healthy" ? <CheckCircle className="h-3 w-3" /> : <HelpCircle className="h-3 w-3" />}
              {s.name}
            </Badge>
          ))}
        </div>
        <span className="text-sm text-muted-foreground">{user?.email}</span>
        <Avatar className="h-8 w-8">
          <AvatarFallback className="text-xs">{initials}</AvatarFallback>
        </Avatar>
        <Button variant="ghost" size="icon" onClick={logout} title="Logout">
          <LogOut className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}
