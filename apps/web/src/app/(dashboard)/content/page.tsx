"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { FileText } from "lucide-react";
import { api } from "@/lib/api";

interface ContentItem {
  id: string;
  project_id: string;
  type: string;
  status: string;
  title: string;
  body?: string;
  created_at?: string;
}

export default function ContentPage() {
  const { data: items = [], isLoading } = useQuery({
    queryKey: ["content"],
    queryFn: () => api.get<ContentItem[]>("/content"),
  });

  const grouped = items.reduce<Record<string, ContentItem[]>>((acc, item) => {
    (acc[item.status] ??= []).push(item);
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Content Studio</h1>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-5">
          {Object.entries(grouped).map(([status, list]) => (
            <Card key={status} className="flex flex-col">
              <CardHeader>
                <CardTitle className="flex items-center justify-between text-base">
                  <span className="capitalize">{status}</span>
                  <Badge variant="secondary">{list.length}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="flex-1 space-y-2">
                {list.map((item) => (
                  <div key={item.id} className="rounded-lg border p-2">
                    <div className="flex items-start gap-2">
                      <FileText className="mt-0.5 h-4 w-4 text-muted-foreground" />
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">{item.title}</p>
                        <p className="text-xs text-muted-foreground">{item.type}</p>
                      </div>
                    </div>
                  </div>
                ))}
                {list.length === 0 && <p className="text-xs text-muted-foreground">Empty</p>}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
