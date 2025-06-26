import { HttpEventType, HttpResponse } from '@angular/common/http';
import { Component } from '@angular/core';
import { FileService } from '../../shared/services/file.service';
import { MatSnackBar } from '@angular/material/snack-bar';

@Component({
  selector: 'app-home',
  templateUrl: './home.component.html',
  styleUrl: './home.component.css'
})
export class HomeComponent {
  selectedFile: File | null = null;
  uploadProgress = 0;
  uploading = false;
  downloadLink: string | null = null;

  constructor(private fileService: FileService, private snackBar: MatSnackBar) {}

  onFileSelected(event: any): void {
    this.selectedFile = event.target.files[0];
    this.reset();
  }
  
  onDragOver(event: DragEvent) { event.preventDefault(); }
  onDragLeave(event: DragEvent) { event.preventDefault(); }
  onDrop(event: DragEvent) {
    event.preventDefault();
    if (event.dataTransfer?.files.length) {
      this.selectedFile = event.dataTransfer.files[0];
      this.reset();
    }
  }

  onUpload(): void {
    if (!this.selectedFile) return;

    this.uploading = true;
    this.uploadProgress = 0;
    this.downloadLink = null;

    this.fileService.upload(this.selectedFile).subscribe({
      next: (event: any) => {
        if (event.type === HttpEventType.UploadProgress) {
          this.uploadProgress = Math.round(100 * event.loaded / event.total!);
        } else if (event instanceof HttpResponse) {
          // This is the response from the FINAL call to our backend /finalize
          this.downloadLink = window.location.origin + event.body.download_link;
          this.uploading = false;
          this.snackBar.open('Upload finalized!', 'Close', { duration: 3000 });
        }
      },
      error: (err) => {
        console.error(err);
        this.snackBar.open('Upload failed! Please check console and try again.', 'Close', { duration: 5000 });
        this.reset();
      }
    });
  }

  copyLink(link: string) {
    navigator.clipboard.writeText(link).then(() => {
      this.snackBar.open('Link copied to clipboard!', 'Close', { duration: 2000 });
    });
  }

  reset() {
    this.uploadProgress = 0;
    this.downloadLink = null;
    this.uploading = false;
  }
}
