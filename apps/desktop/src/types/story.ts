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
  identity: string;
  appearance: string;
  hairstyle: string;
  costume: string;
  build: string;
  marks: string;
  personality: string;
  style: string;
  reference_prompt: string;
  asset_id: string;
}

export interface BibleLocation {
  name: string;
  description: string;
  environment: string;
  time: string;
  lighting: string;
  style: string;
  reference_prompt: string;
  asset_id: string;
}

export interface BibleProp {
  name: string;
  description: string;
  material: string;
  reference: string;
  reference_prompt: string;
  asset_id: string;
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

export type AssetType = "character" | "location" | "prop";

export interface AssetImageSpec {
  aspect_ratio: string;
  width: number;
  height: number;
  label: string;
}

export interface AssetCard {
  asset_type: AssetType;
  asset_id: string;
  name: string;
  image_spec: AssetImageSpec;
  reference_prompt: string;
  fields: BibleCharacter | BibleLocation | BibleProp;
}

export interface AssetGenerateJob {
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
