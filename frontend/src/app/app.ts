import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  DestroyRef,
  ElementRef,
  inject,
  OnDestroy,
  OnInit,
  signal,
  ViewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  LucideAlertCircle as AlertCircle,
  LucideArrowUp as ArrowUp,
  LucideBookOpen as BookOpen,
  LucideBot as Bot,
  LucideChevronRight as ChevronRight,
  LucideDatabase as Database,
  LucideDynamicIcon,
  LucideFileText as FileText,
  LucideHash as Hash,
  LucideLayers as Layers,
  LucideLibrary as Library,
  LucideMenu as Menu,
  LucideMessageSquare as MessageSquare,
  LucidePanelRight as PanelRight,
  LucidePlus as Plus,
  LucideRotateCcw as RotateCcw,
  LucideSearch as Search,
  LucideSparkles as Sparkles,
  LucideTrash2 as Trash2,
  LucideUser as User,
  LucideX as X,
} from '@lucide/angular';
import { finalize } from 'rxjs';

import { EvidencePanelComponent } from './components/evidence-panel/evidence-panel.component';
import { UploadDialogComponent } from './components/upload-dialog/upload-dialog.component';
import {
  ApiErrorResponse,
  BookSummary,
  ChatTurn,
  Evidence,
  HealthResponse,
  QuestionStreamEvent,
  UploadRequest,
} from './models/api.models';
import { ReadingApiService } from './services/reading-api.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    EvidencePanelComponent,
    LucideDynamicIcon,
    UploadDialogComponent,
  ],
  templateUrl: './app.html',
  styleUrl: './app.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppComponent implements OnInit, OnDestroy {
  private readonly api = inject(ReadingApiService);
  private readonly destroyRef = inject(DestroyRef);

  @ViewChild('conversation')
  private conversation?: ElementRef<HTMLElement>;

  @ViewChild('questionInput')
  private questionInput?: ElementRef<HTMLTextAreaElement>;

  readonly bookIcon = BookOpen;
  readonly botIcon = Bot;
  readonly userIcon = User;
  readonly messageIcon = MessageSquare;
  readonly layersIcon = Layers;
  readonly libraryIcon = Library;
  readonly searchIcon = Search;
  readonly plusIcon = Plus;
  readonly trashIcon = Trash2;
  readonly menuIcon = Menu;
  readonly closeIcon = X;
  readonly sparklesIcon = Sparkles;
  readonly arrowUpIcon = ArrowUp;
  readonly rotateIcon = RotateCcw;
  readonly alertIcon = AlertCircle;
  readonly databaseIcon = Database;
  readonly panelIcon = PanelRight;
  readonly fileIcon = FileText;
  readonly hashIcon = Hash;
  readonly chevronIcon = ChevronRight;

  readonly books = signal<BookSummary[]>([]);
  readonly selectedBookId = signal<string | null>(null);
  readonly searchTerm = signal('');
  readonly health = signal<HealthResponse | null>(null);
  readonly healthError = signal(false);
  readonly loadingBooks = signal(true);
  readonly bookLoadError = signal('');
  readonly turns = signal<ChatTurn[]>([]);
  readonly activeEvidence = signal<Evidence[]>([]);
  readonly selectedEvidenceIndex = signal<number | null>(null);
  readonly question = signal('');
  readonly asking = signal(false);
  readonly uploadOpen = signal(false);
  readonly uploading = signal(false);
  readonly uploadError = signal('');
  readonly deleteTarget = signal<BookSummary | null>(null);
  readonly deleting = signal(false);
  readonly sidebarOpen = signal(false);
  readonly evidenceOpen = signal(false);
  readonly toastMessage = signal('');
  readonly toastTone = signal<'success' | 'error'>('success');

  readonly filteredBooks = computed(() => {
    const needle = this.searchTerm().trim().toLowerCase();
    if (!needle) {
      return this.books();
    }
    return this.books().filter(
      (book) =>
        book.title.toLowerCase().includes(needle) ||
        book.source_name.toLowerCase().includes(needle),
    );
  });

  readonly selectedBook = computed(() => {
    const selectedId = this.selectedBookId();
    return this.books().find((book) => book.id === selectedId) ?? null;
  });

  readonly totalChunks = computed(() =>
    this.books().reduce((total, book) => total + book.chunk_count, 0),
  );

  readonly currentScopeTitle = computed(
    () => this.selectedBook()?.title ?? '全部书籍',
  );

  readonly currentScopeEyebrow = computed(() =>
    this.selectedBook() ? '当前书籍' : '跨书检索',
  );

  readonly currentScopeMeta = computed(() => {
    const book = this.selectedBook();
    if (book) {
      return `${book.source_name} · ${this.formatNumber(book.chunk_count)} 个片段`;
    }
    if (!this.books().length) {
      return '上传第一本书开始';
    }
    return `${this.books().length} 本书 · ${this.formatNumber(this.totalChunks())} 个片段`;
  });

  readonly connectionLabel = computed(() => {
    if (this.healthError()) {
      return '服务离线';
    }
    const health = this.health();
    if (!health) {
      return '正在连接';
    }
    return health.generated_answers_enabled ? 'Gemini 已连接' : '本地检索';
  });

  readonly connectionOffline = computed(
    () =>
      this.healthError() ||
      (this.health() !== null && this.health()?.status !== 'ok'),
  );

  readonly canSubmit = computed(
    () =>
      Boolean(this.question().trim()) &&
      !this.asking() &&
      this.books().length > 0,
  );

  readonly evidenceCount = computed(() => this.activeEvidence().length);
  readonly questionLength = computed(() => this.question().length);

  readonly emptyTitle = computed(() => {
    if (!this.books().length) {
      return '书架还空着';
    }
    return this.selectedBook()
      ? `向《${this.selectedBook()?.title}》提问`
      : '从全部书籍中寻找答案';
  });

  readonly suggestions = computed(() => {
    const scope = this.selectedBook() ? '这本书' : '这些书';
    return [
      {
        icon: Sparkles,
        title: '核心概括',
        prompt: `概括${scope}的核心内容，并说明最重要的三个观点。`,
      },
      {
        icon: Hash,
        title: '关键线索',
        prompt: `梳理${scope}中的主要人物和关键关系。`,
      },
      {
        icon: Layers,
        title: '结构脉络',
        prompt: `按照发展顺序梳理${scope}的章节或情节结构。`,
      },
      {
        icon: MessageSquare,
        title: '细读片段',
        prompt: '找出最值得细读的三个片段，并解释原因。',
      },
    ];
  });

  private toastTimer?: number;
  private streamScrollFrame?: number;

  ngOnInit(): void {
    this.loadHealth();
    this.loadBooks();
  }

  ngOnDestroy(): void {
    if (this.toastTimer !== undefined) {
      window.clearTimeout(this.toastTimer);
    }
    if (this.streamScrollFrame !== undefined) {
      window.cancelAnimationFrame(this.streamScrollFrame);
    }
  }

  selectBook(bookId: string): void {
    if (this.asking()) {
      return;
    }
    if (this.selectedBookId() === bookId) {
      this.sidebarOpen.set(false);
      return;
    }
    this.selectedBookId.set(bookId);
    this.resetThread();
    this.sidebarOpen.set(false);
    this.focusComposer();
  }

  selectAllBooks(): void {
    if (this.asking()) {
      return;
    }
    if (this.selectedBookId() === null) {
      this.sidebarOpen.set(false);
      return;
    }
    this.selectedBookId.set(null);
    this.resetThread();
    this.sidebarOpen.set(false);
    this.focusComposer();
  }

  updateSearch(event: Event): void {
    this.searchTerm.set((event.target as HTMLInputElement).value);
  }

  reloadBooks(): void {
    this.loadHealth();
    this.loadBooks();
  }

  openUploadDialog(): void {
    this.uploadError.set('');
    this.uploadOpen.set(true);
  }

  closeUploadDialog(): void {
    if (!this.uploading()) {
      this.uploadOpen.set(false);
      this.uploadError.set('');
    }
  }

  uploadBook(request: UploadRequest): void {
    if (this.uploading()) {
      return;
    }
    this.uploading.set(true);
    this.uploadError.set('');
    this.api
      .uploadBook(request.file, request.title)
      .pipe(
        takeUntilDestroyed(this.destroyRef),
        finalize(() => this.uploading.set(false)),
      )
      .subscribe({
        next: ({ book }) => {
          this.books.update((books) => [
            book,
            ...books.filter((item) => item.id !== book.id),
          ]);
          this.selectedBookId.set(book.id);
          this.resetThread();
          this.uploadOpen.set(false);
          this.showToast(`《${book.title}》已加入书库`);
          this.focusComposer();
        },
        error: (error: unknown) => {
          this.uploadError.set(this.errorMessage(error));
        },
      });
  }

  requestDelete(book: BookSummary, event: MouseEvent): void {
    event.stopPropagation();
    this.deleteTarget.set(book);
  }

  cancelDelete(): void {
    if (!this.deleting()) {
      this.deleteTarget.set(null);
    }
  }

  confirmDelete(): void {
    const book = this.deleteTarget();
    if (!book || this.deleting()) {
      return;
    }
    this.deleting.set(true);
    this.api
      .deleteBook(book.id)
      .pipe(
        takeUntilDestroyed(this.destroyRef),
        finalize(() => this.deleting.set(false)),
      )
      .subscribe({
        next: () => {
          const remaining = this.books().filter((item) => item.id !== book.id);
          this.books.set(remaining);
          if (this.selectedBookId() === book.id) {
            this.selectedBookId.set(remaining[0]?.id ?? null);
            this.resetThread();
          }
          this.deleteTarget.set(null);
          this.showToast(`《${book.title}》已移出书库`);
        },
        error: (error: unknown) => {
          this.deleteTarget.set(null);
          this.showToast(this.errorMessage(error), 'error');
        },
      });
  }

  submitQuestion(prompt?: string): void {
    const cleanQuestion = (prompt ?? this.question()).trim();
    if (!cleanQuestion || this.asking() || !this.books().length) {
      return;
    }

    const turn: ChatTurn = {
      id: crypto.randomUUID(),
      question: cleanQuestion,
      answer: '',
      mode: null,
      model: null,
      evidence: [],
      status: 'pending',
      error: null,
    };
    this.turns.update((turns) => [...turns, turn]);
    this.question.set('');
    this.resizeComposer();
    this.asking.set(true);

    this.api
      .streamQuestion(cleanQuestion, this.selectedBookId(), 3)
      .pipe(
        takeUntilDestroyed(this.destroyRef),
        finalize(() => this.asking.set(false)),
      )
      .subscribe({
        next: (event) => this.handleStreamEvent(turn.id, event),
        error: (error: unknown) => {
          const message = this.errorMessage(error);
          this.updateTurn(turn.id, {
            status: 'error',
            error: message,
          });
          this.showToast(message, 'error');
          this.scrollToLatest();
        },
      });
  }

  retryTurn(turn: ChatTurn): void {
    this.turns.update((turns) => turns.filter((item) => item.id !== turn.id));
    this.submitQuestion(turn.question);
  }

  clearConversation(): void {
    if (this.asking()) {
      return;
    }
    this.resetThread();
    this.focusComposer();
  }

  onComposerInput(event: Event): void {
    const textarea = event.target as HTMLTextAreaElement;
    this.question.set(textarea.value);
    this.resizeComposer();
  }

  onComposerKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.submitQuestion();
    }
  }

  selectEvidence(index: number): void {
    this.selectedEvidenceIndex.set(index);
    if (window.matchMedia('(max-width: 1100px)').matches) {
      this.evidenceOpen.set(true);
    }
  }

  selectCitation(index: number): void {
    this.selectedEvidenceIndex.set(index);
    this.evidenceOpen.set(true);
  }

  toggleSidebar(): void {
    this.sidebarOpen.update((open) => !open);
    if (this.sidebarOpen()) {
      this.evidenceOpen.set(false);
    }
  }

  toggleEvidence(): void {
    this.evidenceOpen.update((open) => !open);
    if (this.evidenceOpen()) {
      this.sidebarOpen.set(false);
    }
  }

  closeMobilePanels(): void {
    this.sidebarOpen.set(false);
    this.evidenceOpen.set(false);
  }

  modeLabel(mode: string | null): string {
    if (mode === 'generated') {
      return 'Gemini';
    }
    if (mode === 'extractive') {
      return '原文摘录';
    }
    return mode ?? '';
  }

  bookInitial(book: BookSummary): string {
    return book.title.trim().charAt(0).toUpperCase() || '书';
  }

  formatNumber(value: number): string {
    return new Intl.NumberFormat('zh-CN').format(value);
  }

  indexLabel(index: number): string {
    return String(index + 1).padStart(2, '0');
  }

  closeToast(): void {
    this.toastMessage.set('');
    if (this.toastTimer !== undefined) {
      window.clearTimeout(this.toastTimer);
      this.toastTimer = undefined;
    }
  }

  private loadHealth(): void {
    this.api
      .getHealth()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (health) => {
          this.health.set(health);
          this.healthError.set(false);
        },
        error: () => this.healthError.set(true),
      });
  }

  private loadBooks(): void {
    this.loadingBooks.set(true);
    this.bookLoadError.set('');
    this.api
      .listBooks()
      .pipe(
        takeUntilDestroyed(this.destroyRef),
        finalize(() => this.loadingBooks.set(false)),
      )
      .subscribe({
        next: ({ items }) => {
          this.books.set(items);
          const current = this.selectedBookId();
          if (!current || !items.some((book) => book.id === current)) {
            this.selectedBookId.set(items[0]?.id ?? null);
          }
        },
        error: (error: unknown) => {
          const message = this.errorMessage(error);
          this.bookLoadError.set(message);
          this.showToast(message, 'error');
        },
      });
  }

  private resetThread(): void {
    this.turns.set([]);
    this.activeEvidence.set([]);
    this.selectedEvidenceIndex.set(null);
    this.question.set('');
    this.evidenceOpen.set(false);
    this.resizeComposer();
  }

  private updateTurn(turnId: string, patch: Partial<ChatTurn>): void {
    this.turns.update((turns) =>
      turns.map((turn) => (turn.id === turnId ? { ...turn, ...patch } : turn)),
    );
  }

  private handleStreamEvent(
    turnId: string,
    event: QuestionStreamEvent,
  ): void {
    switch (event.type) {
      case 'meta':
        this.updateTurn(turnId, {
          evidence: event.evidence,
        });
        this.activeEvidence.set(event.evidence);
        this.selectedEvidenceIndex.set(
          event.evidence.length ? 0 : null,
        );
        break;
      case 'delta':
        this.appendAnswer(turnId, event);
        break;
      case 'done':
        this.updateTurn(turnId, {
          mode: event.mode,
          model: event.model,
          status: 'done',
        });
        this.scrollToLatest();
        break;
      case 'error':
        this.updateTurn(turnId, {
          status: 'error',
          error: event.message,
        });
        this.showToast(event.message, 'error');
        this.scrollToLatest();
        break;
    }
  }

  private appendAnswer(
    turnId: string,
    event: Extract<QuestionStreamEvent, { type: 'delta' }>,
  ): void {
    this.turns.update((turns) =>
      turns.map((turn) =>
        turn.id === turnId
          ? {
              ...turn,
              answer: turn.answer + event.text,
              mode: event.mode,
              model: event.model,
              status: 'pending',
            }
          : turn,
      ),
    );
    this.scrollDuringStream();
  }

  private scrollDuringStream(): void {
    if (this.streamScrollFrame !== undefined) {
      return;
    }
    this.streamScrollFrame = window.requestAnimationFrame(() => {
      const element = this.conversation?.nativeElement;
      if (element) {
        element.scrollTop = element.scrollHeight;
      }
      this.streamScrollFrame = undefined;
    });
  }

  private scrollToLatest(): void {
    window.setTimeout(() => {
      const element = this.conversation?.nativeElement;
      if (element) {
        element.scrollTo({ top: element.scrollHeight, behavior: 'smooth' });
      }
    });
  }

  private focusComposer(): void {
    window.setTimeout(() => this.questionInput?.nativeElement.focus());
  }

  private resizeComposer(): void {
    window.setTimeout(() => {
      const textarea = this.questionInput?.nativeElement;
      if (!textarea) {
        return;
      }
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 148)}px`;
    });
  }

  private showToast(
    message: string,
    tone: 'success' | 'error' = 'success',
  ): void {
    this.toastMessage.set(message);
    this.toastTone.set(tone);
    if (this.toastTimer !== undefined) {
      window.clearTimeout(this.toastTimer);
    }
    this.toastTimer = window.setTimeout(() => {
      this.toastMessage.set('');
      this.toastTimer = undefined;
    }, 3600);
  }

  private errorMessage(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      const body = error.error as ApiErrorResponse | null;
      if (body?.message) {
        return body.message;
      }
      if (error.status === 0) {
        return '后端服务暂时不可用';
      }
      if (error.status === 413) {
        return '文档超过上传限制';
      }
      return `请求失败（${error.status}）`;
    }
    if (error instanceof Error && error.message) {
      return error.message;
    }
    return '请求失败，请稍后重试';
  }
}
