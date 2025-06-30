// import { Component, OnDestroy } from '@angular/core';
// import { UploadService } from '../../shared/services/upload.service';
// import { Subscription } from 'rxjs';
// import { MatSnackBar } from '@angular/material/snack-bar';

// @Component({
//   selector: 'app-home',
//   templateUrl: './home.component.html',
// })
// export class HomeComponent implements OnDestroy {
//   selectedFile: File | null = null;
//   uploadProgress = 0;
//   uploading = false;
//   uploadSuccess = false;
//   private progressSub: Subscription;

//   constructor(private uploadService: UploadService, private snackBar: MatSnackBar) {
//     // Subscribe to progress updates from the service
//     this.progressSub = this.uploadService.uploadProgress$.subscribe({
//       next: (progress) => {
//         this.uploadProgress = progress;
//         if (progress === 100) {
//           this.uploading = false;
//           this.uploadSuccess = true;
//           this.snackBar.open('File upload complete!', 'Close', { duration: 3000 });
//         }
//       },
//       error: (err) => {
//         this.uploading = false;
//         this.snackBar.open(`Upload Failed: ${err}`, 'Close', { duration: 5000 });
//         this.reset();
//       }
//     });
//   }

//   onFileSelected(event: any): void {
//     this.selectedFile = event.target.files[0];
//     this.reset();
//   }

//   onDragOver(event: DragEvent) { event.preventDefault(); }
//   onDragLeave(event: DragEvent) { event.preventDefault(); }

//   onDrop(event: DragEvent) {
//     event.preventDefault();
//     if (event.dataTransfer?.files.length) {
//       this.selectedFile = event.dataTransfer.files[0];
//       this.reset();
//     }
//   }

//   onUpload(): void {
//     if (!this.selectedFile) return;

//     this.uploading = true;
//     this.uploadSuccess = false;
//     this.uploadProgress = 0;

//     // The component's job is just to start the upload.
//     // The progress subscription will handle the rest.
//     this.uploadService.upload(this.selectedFile).subscribe({
//       next: () => {
//         console.log('Upload initiated successfully.');
//       },
//       error: (err) => {
//         // This error is for the initiation step only
//         this.uploading = false;
//         this.snackBar.open('Could not start upload. Please check the console.', 'Close', { duration: 3000 });
//       }
//     });
//   }
  
//   // We no longer need a download link immediately, as the processing happens in the background
//   // The UI can be updated to reflect this.

//   reset() {
//     this.uploadProgress = 0;
//     this.uploading = false;
//     this.uploadSuccess = false;
//   }

//   ngOnDestroy(): void {
//     // Unsubscribe to prevent memory leaks
//     if (this.progressSub) {
//       this.progressSub.unsubscribe();
//     }
//   }
// }



import { Component, OnDestroy } from '@angular/core';
import { UploadService } from '../../shared/services/upload.service'; // Adjust path if needed
import { Subscription } from 'rxjs';
import { MatSnackBar } from '@angular/material/snack-bar';

// Define the different states our component can be in for clean UI management
type UploadState = 'idle' | 'uploading' | 'processing' | 'success' | 'error';

@Component({
  selector: 'app-home',
  templateUrl: './home.component.html',
})
export class HomeComponent implements OnDestroy {
  // State management
  public currentState: UploadState = 'idle';
  public selectedFile: File | null = null;
  private lastFileId = '';
  
  // Progress tracking
  public browserUploadProgress = 0;
  public serverProcessingProgress = 0;
  
  // Final result
  public finalDownloadLink: string | null = null;
  public errorMessage: string | null = null;

  // Subscriptions to manage
  private uploadInitiationSub?: Subscription;
  private browserProgressSub?: Subscription;
  private serverProgressSub?: Subscription;

  constructor(private uploadService: UploadService, private snackBar: MatSnackBar) {}

  onFileSelected(event: any): void {
    const fileList = (event.target as HTMLInputElement).files;
    if (fileList && fileList.length > 0) {
        this.selectedFile = fileList[0];
        this.reset();
    }
  }

  onUpload(): void {
    if (!this.selectedFile) return;

    this.reset();
    this.currentState = 'uploading';

    // ---- STAGE 1: BROWSER-TO-SERVER UPLOAD ----
    // Subscribe to the progress of the first hop
    this.browserProgressSub = this.uploadService.browserUploadProgress$.subscribe({
        next: progress => this.browserUploadProgress = progress,
        error: err => {
            this.currentState = 'error';
            this.errorMessage = err;
        },
        complete: () => {
            // When the browser upload is 100% complete, switch to the next stage
            this.currentState = 'processing';
            // We use the fileId captured from the initiation call
            this.listenForServerProgress(this.lastFileId);
        }
    });

    // Initiate the upload process. This call returns the fileId we need.
    let lastFileId = '';
    this.uploadInitiationSub = this.uploadService.upload(this.selectedFile).subscribe({
      next: (response) => {
        this.lastFileId = response.file_id; // <-- USE "this." here
        console.log(`Upload initiated. File ID: ${this.lastFileId}`);
      },
      error: (err) => {
        this.currentState = 'error';
        this.errorMessage = 'Could not start upload. Is the server running?';
      }
    });
  }

  // ---- STAGE 2: SERVER-TO-DRIVE PROGRESS ----
  listenForServerProgress(fileId: string): void {
    if (!fileId) {
        this.currentState = 'error';
        this.errorMessage = 'File ID was not received. Cannot track progress.';
        return;
    }
    
    this.serverProgressSub = this.uploadService.listenForServerProgress(fileId).subscribe({
      next: (message) => {
        if (message.type === 'progress') {
          this.serverProcessingProgress = message.value;
        } else if (message.type === 'success') {
          this.currentState = 'success';
          this.finalDownloadLink = message.value;
          this.snackBar.open('File is ready!', 'Close', { duration: 5000 });
        } else if (message.type === 'error') {
          this.currentState = 'error';
          this.errorMessage = message.value;
        }
      },
      error: (err) => {
        this.currentState = 'error';
        this.errorMessage = 'Lost connection to server during processing.';
      }
    });
  }

  reset(): void {
    this.currentState = this.selectedFile ? 'idle' : 'idle';
    this.browserUploadProgress = 0;
    this.serverProcessingProgress = 0;
    this.finalDownloadLink = null;
    this.errorMessage = null;
    // Unsubscribe from all potential subscriptions to prevent memory leaks
    this.uploadInitiationSub?.unsubscribe();
    this.browserProgressSub?.unsubscribe();
    this.serverProgressSub?.unsubscribe();
  }

  copyLink(link: string): void {
    navigator.clipboard.writeText(link).then(() => {
      this.snackBar.open('Link copied to clipboard!', 'Close', { duration: 2000 });
    });
  }

  // --- Drag and Drop Handlers ---
  onDragOver(event: DragEvent) { event.preventDefault(); }
  onDragLeave(event: DragEvent) { event.preventDefault(); }
  onDrop(event: DragEvent) {
    event.preventDefault();
    if (event.dataTransfer?.files.length) {
      this.selectedFile = event.dataTransfer.files[0];
      this.reset();
    }
  }

  ngOnDestroy(): void {
    this.reset();
  }
}