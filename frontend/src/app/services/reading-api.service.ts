import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import {
  BookListResponse,
  Evidence,
  HealthResponse,
  QuestionStreamEvent,
  QuestionResponse,
  UploadBookResponse,
} from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class ReadingApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api/v1';

  getHealth(): Observable<HealthResponse> {
    return this.http.get<HealthResponse>(`${this.baseUrl}/health`);
  }

  listBooks(): Observable<BookListResponse> {
    return this.http.get<BookListResponse>(`${this.baseUrl}/books`);
  }

  uploadBook(file: File, title: string): Observable<UploadBookResponse> {
    const formData = new FormData();
    formData.append('file', file);
    if (title.trim()) {
      formData.append('title', title.trim());
    }
    return this.http.post<UploadBookResponse>(
      `${this.baseUrl}/books`,
      formData,
    );
  }

  deleteBook(bookId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/books/${bookId}`);
  }

  askQuestion(
    question: string,
    bookId: string | null,
    topK = 3,
  ): Observable<QuestionResponse> {
    return this.http.post<QuestionResponse>(`${this.baseUrl}/questions`, {
      question,
      book_id: bookId,
      top_k: topK,
    });
  }

  streamQuestion(
    question: string,
    bookId: string | null,
    topK = 3,
  ): Observable<QuestionStreamEvent> {
    return new Observable<QuestionStreamEvent>((subscriber) => {
      const controller = new AbortController();

      const consume = async (): Promise<void> => {
        try {
          const response = await fetch(`${this.baseUrl}/questions/stream`, {
            method: 'POST',
            headers: {
              Accept: 'text/event-stream',
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              question,
              book_id: bookId,
              top_k: topK,
            }),
            signal: controller.signal,
          });

          if (!response.ok) {
            throw new Error(await this.httpError(response));
          }
          if (!response.body) {
            throw new Error('浏览器不支持流式响应');
          }

          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = '';
          let finished = false;

          while (!finished) {
            const { done, value } = await reader.read();
            buffer += decoder.decode(value, { stream: !done });
            let frameMatch = /\r?\n\r?\n/.exec(buffer);

            while (frameMatch && frameMatch.index !== undefined) {
              const frame = buffer.slice(0, frameMatch.index);
              buffer = buffer.slice(frameMatch.index + frameMatch[0].length);
              const event = this.parseSseFrame(frame);
              if (event) {
                subscriber.next(event);
                if (event.type === 'done' || event.type === 'error') {
                  finished = true;
                  break;
                }
              }
              frameMatch = /\r?\n\r?\n/.exec(buffer);
            }

            if (done) {
              break;
            }
          }

          await reader.cancel();
          subscriber.complete();
        } catch (error) {
          if (!controller.signal.aborted) {
            subscriber.error(error);
          }
        }
      };

      void consume();
      return () => controller.abort();
    });
  }

  private parseSseFrame(frame: string): QuestionStreamEvent | null {
    let eventName = 'message';
    const dataLines: string[] = [];

    for (const line of frame.split(/\r?\n/)) {
      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trimStart());
      }
    }

    if (!dataLines.length) {
      return null;
    }

    const data = JSON.parse(dataLines.join('\n')) as Record<string, unknown>;
    switch (eventName) {
      case 'meta':
        return {
          type: 'meta',
          question: String(data['question'] ?? ''),
          evidence: (data['evidence'] ?? []) as Evidence[],
        };
      case 'delta':
        return {
          type: 'delta',
          text: String(data['text'] ?? ''),
          mode: String(data['mode'] ?? 'extractive'),
          model: data['model'] ? String(data['model']) : null,
        };
      case 'done':
        return {
          type: 'done',
          mode: String(data['mode'] ?? 'extractive'),
          model: data['model'] ? String(data['model']) : null,
        };
      case 'error':
        return {
          type: 'error',
          code: String(data['code'] ?? 'stream_failed'),
          message: String(data['message'] ?? '流式回答失败'),
        };
      default:
        return null;
    }
  }

  private async httpError(response: Response): Promise<string> {
    try {
      const body = (await response.json()) as { message?: string };
      if (body.message) {
        return body.message;
      }
    } catch {
      // The fallback below covers non-JSON errors from a proxy or gateway.
    }
    return `请求失败（${response.status}）`;
  }
}
