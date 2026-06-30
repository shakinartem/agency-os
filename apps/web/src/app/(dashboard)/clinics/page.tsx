"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface Project {
  id: string;
  name: string;
  slug: string;
  status: string;
  description?: string;
}

export default function ClinicsPage() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");

  const { data: projects = [], isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.get<Project[]>("/projects"),
  });

  const create = useMutation({
    mutationFn: (body: { name: string; slug: string; description?: string }) =>
      api.post<Project>("/projects", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects"] }),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    create.mutate({ name, slug, description });
    setName("");
    setSlug("");
    setDescription("");
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Clinics / Projects</h1>

      <Card>
        <CardHeader>
          <CardTitle>Create Clinic</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="grid gap-3 md:grid-cols-4">
            <Input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} required />
            <Input placeholder="Slug" value={slug} onChange={(e) => setSlug(e.target.value)} required />
            <Input placeholder="Description" value={description} onChange={(e) => setDescription(e.target.value)} />
            <Button type="submit" disabled={create.isPending}>Create</Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Existing Clinics</CardTitle></CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (
            <div className="space-y-2">
              {projects.map((p) => (
                <div key={p.id} className="flex items-center justify-between rounded-lg border p-3">
                  <div>
                    <p className="font-medium">{p.name}</p>
                    <p className="text-xs text-muted-foreground">{p.slug} — {p.description}</p>
                  </div>
                  <Badge>{p.status}</Badge>
                </div>
              ))}
              {projects.length === 0 && <p className="text-sm text-muted-foreground">No projects yet.</p>}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
