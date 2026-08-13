export interface Novel {
  id: string;
  project_id: string;
  title: string;
  source_type: string;
  chapter_count: number;
  created_at: string;
  updated_at: string;
}

export interface Chapter {
  id: string;
  novel_id: string;
  title: string;
  content: string;
  order_index: number;
  created_at: string;
  updated_at: string;
}

export interface NovelDetail {
  novel: Novel;
  chapters: Chapter[];
}
