export interface Episode {
  id: string;
  project_id: string;
  novel_id: string | null;
  title: string;
  summary: string;
  order_index: number;
  source_chapter_index: number | null;
  created_at: string;
  updated_at: string;
}

export interface Scene {
  id: string;
  project_id: string;
  episode_id: string | null;
  novel_id: string | null;
  title: string;
  order_index: number;
  slugline: string;
  action: string;
  dialogue: string;
  created_at: string;
  updated_at: string;
}

export interface Shot {
  id: string;
  project_id: string;
  scene_id: string | null;
  shot_number: number | null;
  order_index: number;
  shot_type: string;
  camera: string;
  characters: string;
  action: string;
  lighting: string;
  dialogue: string;
  duration: number;
  prompt: string;
  created_at: string;
  updated_at: string;
}

export interface EpisodeDetail {
  episode: Episode;
  scenes: Scene[];
}

export interface SceneDetail {
  scene: Scene;
  shots: Shot[];
}

export interface AiEpisodePlan {
  title: string;
  summary: string;
}

export interface AiSceneScript {
  title: string;
  slugline: string;
  action: string;
  dialogue: string;
}

export interface AiEpisodeScriptResult {
  episode: AiEpisodePlan;
  scenes: AiSceneScript[];
}

export interface AiShotOut {
  shot_type: string;
  camera: string;
  characters: string;
  action: string;
  lighting: string;
  dialogue: string;
  duration: number;
  prompt: string;
}

export interface AiShotsResult {
  shots: AiShotOut[];
}
