"use client";

import React, { createContext, useContext, useState } from "react";

interface Project {
  id: string;
  name: string;
  slug?: string;
}

interface ProjectState {
  current: Project | null;
  projects: Project[];
  setCurrent: (p: Project) => void;
  setProjects: (list: Project[]) => void;
}

const ProjectContext = createContext<ProjectState | undefined>(undefined);

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const [current, setCurrent] = useState<Project | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);

  return (
    <ProjectContext.Provider value={{ current, projects, setCurrent, setProjects }}>
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject() {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error("useProject must be used within ProjectProvider");
  return ctx;
}
