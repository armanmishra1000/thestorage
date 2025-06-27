import { Component, OnDestroy } from '@angular/core';
import { UploadService } from '../../shared/services/upload.service';
import { Subscription } from 'rxjs';
import { MatSnackBar } from '@angular/material/snack-bar';

@Component({
  selector: 'app-home',
  templateUrl: './home.component.html',
})
export class HomeComponent implements OnDestroy {
  selectedFile: File | null = null;
  uploadProgress = 0;
  uploading = false;
  uploadSuccess = false;
  private progressSub: Subscription;

  constructor(private uploadService: UploadService, private snackBar: MatSnackBar) {
    // Subscribe to progress updates from the service
    this.progressSub = this.uploadService.uploadProgress$.subscribe({
      next: (progress) => {
        this.uploadProgress = progress;
        if (progress === 100) {
          this.uploading = false;
          this.uploadSuccess = true;
          this.snackBar.open('File upload complete!', 'Close', { duration: 3000 });
        }
      },
      error: (err) => {
        this.uploading = false;
        this.snackBar.open(`Upload Failed: ${err}`, 'Close', { duration: 5000 });
        this.reset();
      }
    });
  }

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
    this.uploadSuccess = false;
    this.uploadProgress = 0;

    // The component's job is just to start the upload.
    // The progress subscription will handle the rest.
    this.uploadService.upload(this.selectedFile).subscribe({
      next: () => {
        console.log('Upload initiated successfully.');
      },
      error: (err) => {
        // This error is for the initiation step only
        this.uploading = false;
        this.snackBar.open('Could not start upload. Please check the console.', 'Close', { duration: 3000 });
      }
    });
  }
  
  // We no longer need a download link immediately, as the processing happens in the background
  // The UI can be updated to reflect this.

  reset() {
    this.uploadProgress = 0;
    this.uploading = false;
    this.uploadSuccess = false;
  }

  ngOnDestroy(): void {
    // Unsubscribe to prevent memory leaks
    if (this.progressSub) {
      this.progressSub.unsubscribe();
    }
  }
}