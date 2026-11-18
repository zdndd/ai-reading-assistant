import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  Output,
  signal,
} from '@angular/core';
import {
  LucideCheck as Check,
  LucideChevronRight as ChevronRight,
  LucideCopy as Copy,
  LucideDynamicIcon,
  LucideFileText as FileText,
  LucideQuote as Quote,
  LucideX as X,
} from '@lucide/angular';

import { Evidence } from '../../models/api.models';

@Component({
  selector: 'app-evidence-panel',
  standalone: true,
  imports: [LucideDynamicIcon],
  templateUrl: './evidence-panel.component.html',
  styleUrl: './evidence-panel.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EvidencePanelComponent {
  @Input() evidence: Evidence[] = [];
  @Input() selectedIndex: number | null = null;
  @Input() showClose = false;
  @Output() readonly evidenceSelected = new EventEmitter<number>();
  @Output() readonly closed = new EventEmitter<void>();

  readonly quoteIcon = Quote;
  readonly fileIcon = FileText;
  readonly chevronIcon = ChevronRight;
  readonly copyIcon = Copy;
  readonly checkIcon = Check;
  readonly closeIcon = X;
  readonly copiedId = signal<string | null>(null);

  selectEvidence(index: number): void {
    this.evidenceSelected.emit(index);
  }

  scorePercent(item: Evidence): number {
    return Math.round(
      Math.max(4, Math.min(100, ((item.retrieval_score + 1) / 2) * 100)),
    );
  }

  async copyEvidence(item: Evidence, event: MouseEvent): Promise<void> {
    event.stopPropagation();
    try {
      await navigator.clipboard.writeText(item.text);
      this.copiedId.set(item.chunk_id);
      window.setTimeout(() => {
        if (this.copiedId() === item.chunk_id) {
          this.copiedId.set(null);
        }
      }, 1400);
    } catch {
      this.copiedId.set(null);
    }
  }
}
