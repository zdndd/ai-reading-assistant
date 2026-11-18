export interface BookSummary {
  id: string;
  title: string;
  source_name: string;
  character_count: number;
  chunk_count: number;
  created_at: string;
  content_sha256: string;
}

export interface BookListResponse {
  items: BookSummary[];
  total: number;
}

export interface UploadBookResponse {
  book: BookSummary;
}

export interface Evidence {
  chunk_id: string;
  book_id: string;
  book_title: string;
  chunk_index: number;
  text: string;
  retrieval_score: number;
  rerank_score: number | null;
}

export interface QuestionResponse {
  question: string;
  answer: string;
  mode: string;
  model: string | null;
  evidence: Evidence[];
}

export type QuestionStreamEvent =
  | {
      type: 'meta';
      question: string;
      evidence: Evidence[];
    }
  | {
      type: 'delta';
      text: string;
      mode: string;
      model: string | null;
    }
  | {
      type: 'done';
      mode: string;
      model: string | null;
    }
  | {
      type: 'error';
      code: string;
      message: string;
    };

export interface HealthResponse {
  status: string;
  app_name: string;
  environment: string;
  llm_provider: string;
  generated_answers_enabled: boolean;
}

export interface ApiErrorResponse {
  code?: string;
  message?: string;
}

export interface ChatTurn {
  id: string;
  question: string;
  answer: string;
  mode: string | null;
  model: string | null;
  evidence: Evidence[];
  status: 'pending' | 'done' | 'error';
  error: string | null;
}

export interface UploadRequest {
  file: File;
  title: string;
}
