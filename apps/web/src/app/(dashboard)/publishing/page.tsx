"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Calendar } from "lucide-react";
import { api } from "@/lib/api";

interface Publication {
  id: string;
  project_id: string;
  platform: string;
  scheduled_at?: string;
  status: string;
  error?: string;
}

export default function PublishingPage() {
  const { data: pubs = [], isLoading } = useQuery({
    queryKey: ["publications"],
    queryFn: () => api.get<Publication[]>("/publications"),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Publishing</h1>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Publications</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Platform</TableHead>
                    <TableHead>Scheduled</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pubs.map((p) => (
                    <TableRow key={p.id}>
                      <TableCell className="capitalize">{p.platform}</TableCell>
                      <TableCell>{p.scheduled_at ? new Date(p.scheduled_at).toLocaleString() : "—"}</TableCell>
                      <TableCell><Badge>{p.status}</Badge></TableCell>
                    </TableRow>
                  ))}
                  {pubs.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={3} className="text-center text-sm text-muted-foreground">No publications.</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Calendar View (mock)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex h-64 items-center justify-center rounded-lg border-2 border-dashed">
              <div className="text-center text-muted-foreground">
                <Calendar className="mx-auto mb-2 h-8 w-8" />
                <p className="text-sm">Calendar integration placeholder</p>
                <p className="text-xs">{pubs.length} scheduled</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
