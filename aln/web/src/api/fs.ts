import { apiClient } from "./client";

export interface DirListResult {
  current: string;
  parent: string | null;
  dirs: string[];
}

export async function listDirs(path = "~"): Promise<DirListResult> {
  const { data } = await apiClient.get<DirListResult>("/fs/dirs", { params: { path } });
  return data;
}
