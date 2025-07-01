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

// Define the different states our component can be in
type UploadState = 'idle' | 'selected' | 'uploading' | 'success' | 'error';

@Component({
  selector: 'app-home',
  templateUrl: './home.component.html',
})
export class HomeComponent implements OnDestroy {
  // --- State Management ---
  public currentState: UploadState = 'idle';
  public selectedFile: File | null = null;
  
  // --- Progress & Result ---
  public browserUploadProgress = 0;
  public finalDownloadLink: string | null = null;
  public errorMessage: string | null = null;

  // --- Subscriptions ---
  private uploadSub?: Subscription;
  private progressSub?: Subscription;

  constructor(private uploadService: UploadService, private snackBar: MatSnackBar) {}

  onFileSelected(event: any): void {
    const fileList = (event.target as HTMLInputElement).files;
    if (fileList && fileList.length > 0) {
      this.selectedFile = fileList[0];
      this.reset();
      this.currentState = 'selected';
    }
  }

  onUpload(): void {
    if (!this.selectedFile) return;

    this.currentState = 'uploading';
    let fileId = ''; // Variable to hold the ID for this upload

    // Subscribe to progress updates first
    this.progressSub = this.uploadService.browserUploadProgress$.subscribe({
        next: progress => {
            this.browserUploadProgress = progress;
        },
        error: err => {
            this.currentState = 'error';
            this.errorMessage = err;
        },
        complete: () => {
            // This 'complete' now fires when the browser-to-server part is done.
            // At this point, the Celery task is running in the background.
            // We can now show the success message and the link to the user.
            this.currentState = 'success';
            this.snackBar.open('File upload complete! Your link is ready.', 'Close', { duration: 3000 });
        }
    });

    // Initiate the upload process. The most important part is getting the fileId.
    this.uploadSub = this.uploadService.upload(this.selectedFile).subscribe({
      next: (response) => {
        fileId = response.file_id;
        console.log(`Upload initiated. File ID: ${fileId}`);
        
        // ** THE FIX IS HERE: Construct the final link immediately **
        this.finalDownloadLink = `${window.location.origin}/download/${fileId}`;
      },
      error: (err) => {
        this.currentState = 'error';
        this.errorMessage = 'Could not start upload. Is the server running?';
        this.progressSub?.unsubscribe(); // Clean up progress sub on initiation error
      }
    });
  }

  reset(): void {
    this.browserUploadProgress = 0;
    this.finalDownloadLink = null;
    this.errorMessage = null;

    // Set state based on whether a file is selected
    this.currentState = this.selectedFile ? 'selected' : 'idle';
    
    // Unsubscribe from all potential subscriptions
    this.uploadSub?.unsubscribe();
    this.progressSub?.unsubscribe();
  }

  startNewUpload(): void {
    this.selectedFile = null;
    this.reset();
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
    if (this.currentState !== 'uploading' && event.dataTransfer?.files.length) {
      this.selectedFile = event.dataTransfer.files[0];
      this.reset();
      this.currentState = 'selected';
    }
  }

  ngOnDestroy(): void {
    // Final cleanup when the component is destroyed
    this.uploadSub?.unsubscribe();
    this.progressSub?.unsubscribe();
  }
}