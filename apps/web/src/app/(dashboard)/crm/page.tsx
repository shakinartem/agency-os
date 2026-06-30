"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { api } from "@/lib/api";

interface Lead {
  id: string;
  name: string;
  phone?: string;
  status: string;
  source: string;
  project_id: string;
  created_at?: string;
}

export default function CrmPage() {
  const [statusFilter, setStatusFilter] = useState("");
  const { data: leads = [], isLoading } = useQuery({
    queryKey: ["leads", statusFilter],
    queryFn: () => api.get<Lead[]>("/leads" + (statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : "")),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">CRM</h1>

      <Card>
        <CardHeader>
          <CardTitle>Leads</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="mb-4 flex gap-2">
            <Input placeholder="Filter by status (new, contacted…)" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} />
            <Button variant="secondary" onClick={() => setStatusFilter("")}>Clear</Button>
          </div>

          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {leads.map((l) => (
                  <TableRow key={l.id}>
                    <TableCell>{l.name}</TableCell>
                    <TableCell>{l.phone ?? "—"}</TableCell>
                    <TableCell>{l.source}</TableCell>
                    <TableCell><Badge>{l.status}</Badge></TableCell>
                    <TableCell>{l.created_at ? new Date(l.created_at).toLocaleDateString() : "—"}</TableCell>
                  </TableRow>
                ))}
                {leads.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-sm text-muted-foreground">No leads found.</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
