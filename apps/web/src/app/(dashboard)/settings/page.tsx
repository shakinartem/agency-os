"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Settings } from "lucide-react";
import { api } from "@/lib/api";

interface Setting {
  id?: string;
  key: string;
  value?: string;
}

export default function SettingsPage() {
  const qc = useQueryClient();
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");

  const { data: settings = [], isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.get<Setting[]>("/settings"),
  });

  const upsert = useMutation({
    mutationFn: (body: { key: string; value?: string }) =>
      api.put<Setting>(`/settings/${encodeURIComponent(body.key)}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!key) return;
    upsert.mutate({ key, value });
    setKey("");
    setValue("");
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-4 w-4" />
            Update / Create Setting
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex gap-2">
            <Input placeholder="Key" value={key} onChange={(e) => setKey(e.target.value)} className="w-1/3" />
            <Input placeholder="Value" value={value} onChange={(e) => setValue(e.target.value)} className="w-1/2" />
            <Button type="submit" disabled={upsert.isPending}>Save</Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Current Settings</CardTitle></CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (
            <div className="space-y-2">
              {settings.map((s) => (
                <div key={s.key} className="flex items-center justify-between rounded-lg border p-3">
                  <div>
                    <p className="font-mono text-sm font-medium">{s.key}</p>
                    <p className="text-xs text-muted-foreground">{s.value ?? "(empty)"}</p>
                  </div>
                  <Badge>{s.id ? "saved" : "new"}</Badge>
                </div>
              ))}
              {settings.length === 0 && <p className="text-sm text-muted-foreground">No settings found.</p>}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
