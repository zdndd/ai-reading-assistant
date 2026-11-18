import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  EventEmitter,
  HostListener,
  Input,
  Output,
  ViewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  LucideBookOpen as BookOpen,
  LucideDynamicIcon,
  LucideFileText as FileText,
  LucideUpload as Upload,
  LucideX as X,
} from '@lucide/angular';

import { UploadRequest } from '../../models/api.models';

const SUPPORTED_EXTENSIONS = ['.txt', '.md', '.markdown'];
const MAX_FILE_BYTES = 20 * 1024 * 1024;

@Component({
  selector: 'app-upload-dialog',
  standalone: true,
  imports: [FormsModule, LucideDynamicIcon],
  templateUrl: './upload-dialog.component.html',
  styleUrl: './upload-dialog.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class UploadDialogComponent implements AfterViewInit {
  @Input() busy = false;
  @Input() error = '';
  @Output() readonly closed = new EventEmitter<void>();
  @Output() readonly uploadRequested = new EventEmitter<UploadRequest>();

  @ViewChild('fileInput')
  private fileInput?: ElementRef<HTMLInputElement>;

  readonly uploadIcon = Upload;
  readonly fileIcon = FileText;
  readonly bookIcon = BookOpen;
  readonly closeIcon = X;

  file: File | null = null;
  title = '';
  validationError = '';
  dragActive = false;

  ngAfterViewInit(): void {
    window.setTimeout(() => this.fileInput?.nativeElement.focus());
  }

  @HostListener('document:keydown.escape')
  handleEscape(): void {
    if (!this.busy) {
      this.closed.emit();
    }
  }

  openFilePicker(): void {
    this.fileInput?.nativeElement.click();
  }

  onFileChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.acceptFiles(input.files);
    input.value = '';
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragActive = false;
    this.acceptFiles(event.dataTransfer?.files ?? null);
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragActive = true;
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    this.dragActive = false;
  }

  removeFile(): void {
    this.file = null;
    this.validationError = '';
  }

  submit(): void {
    if (!this.file || this.busy) {
      return;
    }
    this.validationError = '';
    this.uploadRequested.emit({ file: this.file, title: this.title.trim() });
  }

  close(): void {
    if (!this.busy) {
      this.closed.emit();
    }
  }

  onBackdropClick(event: MouseEvent): void {
    if (event.target === event.currentTarget) {
      this.close();
    }
  }

  formatBytes(bytes: number): string {
    if (bytes < 1024) {
      return `${bytes} B`;
    }
    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(1)} KB`;
    }
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  private acceptFiles(files: FileList | null): void {
    const file = files?.item(0);
    if (!file) {
      return;
    }
    const extension = `.${file.name.split('.').pop()?.toLowerCase() ?? ''}`;
    if (!SUPPORTED_EXTENSIONS.includes(extension)) {
      this.validationError = '请选择 TXT 或 Markdown 文档';
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      this.validationError = '文档大小不能超过 20 MB';
      return;
    }
    this.file = file;
    this.validationError = '';
    if (!this.title) {
      this.title = file.name.replace(/\.[^.]+$/, '');
    }
  }
}
