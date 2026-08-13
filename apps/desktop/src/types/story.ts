export type AnalysisMode = "full" | "merge";
export type AnalysisStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface BibleCharacter {
  name: string;
  aliases: string[];
  summary: string;
  role_hint: string;
}

export interface BibleLocation {
  name: string;
  description: string;
}

export interface BibleProp {
  name: string;
  description: string;
}

export interface BibleEvent {
  summary: string;
  importance: string;
  characters: string[];
  chapter_index: number;
}

export interface StoryBible {
  synopsis: string;
  characters: BibleCharacter[];
  locations: BibleLocation[];
  props: BibleProp[];
  events: BibleEvent[];
  conflicts: string[];
  plotlines: string[];
  foreshadowing: string[];
}

export interface AnalysisJob {
  job_id: string;
  status: AnalysisStatus;
  progress: number | null;
  detail: string;
  error: string | null;
  created_at: string;
}

export interface AiNovelBrief {
  genre: string;
  audience: string;
  ideas: string;
  complexity: number;
  chapter_count: number;
}

export interface OutlineChapter {
  title: string;
  summary: string;
}

export interface AiOutlineResult {
  title: string;
  chapters: OutlineChapter[];
}

export interface AiChapter {
  title: string;
  content: string;
  summary: string;
}
