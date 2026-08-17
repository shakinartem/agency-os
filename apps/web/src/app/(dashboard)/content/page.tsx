"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { FileText, Gauge, Layers3 } from "lucide-react";

interface ContentItem {
  id: string;
  project_id: string;
  type: string;
  status: string;
  title: string;
  body?: string;
  task?: string;
  topic?: string;
  platforms?: string[];
  quality_score?: number;
  current_version?: number;
  created_at?: string;
}

export default function ContentPage() {
  const { current } = useProject();
  const { data: items = [], isLoading } = useQuery({
    queryKey: ["content", current?.id],
    queryFn: () => api.get<ContentItem[]>(`/content${current?.id ? `?project_id=${current.id}` : ""}`),
    refetchInterval: 5000,
  });

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 text-sm font-medium text-primary"><FileText className="h-4 w-4" /> Review workspace</div>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">Content</h1>
        <p className="mt-2 text-sm text-muted-foreground">Канонические материалы после AI-пайплайна. Версии не перезаписываются: `current_version` указывает на актуальную редакцию.</p>
      </div>

      {isLoading ? <p className="text-sm text-muted-foreground">Loading…</p> : (
        <div className="grid gap-4 xl:grid-cols-2">
          {items.map((item) => (
            <Card key={item.id} className="overflow-hidden">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <CardTitle className="truncate text-base">{item.title}</CardTitle>
                    <p className="mt-1 text-xs text-muted-foreground">{item.type} · {(item.platforms || []).join(", ") || "canonical"}</p>
                  </div>
                  <Badge variant="secondary">{item.status}</Badge>
                </div>
              </CardHeader>
              <CardContent>
                <p className="line-clamp-6 whitespace-pre-wrap text-sm leading-6 text-foreground/85">{item.body || "Текст ещё не сформирован."}</p>
                <div className="mt-4 flex flex-wrap gap-4 border-t pt-3 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1"><Gauge className="h-3.5 w-3.5" /> score {item.quality_score != null ? Math.round(item.quality_score * 100) : "—"}</span>
                  <span className="flex items-center gap-1"><Layers3 className="h-3.5 w-3.5" /> v{item.current_version || 0}</span>
                  {item.topic && <span className="truncate">{item.topic}</span>}
                </div>
              </CardContent>
            </Card>
          ))}
          {items.length === 0 && <div className="xl:col-span-2 rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">Контента пока нет. Запустите production run на экране Factory.</div>}
        </div>
      )}
    </div>
  );
}
