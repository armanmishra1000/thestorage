// // // import { Component, OnDestroy } from '@angular/core';
// // // import { UploadService } from '../../shared/services/upload.service';
// // // import { Subscription } from 'rxjs';
// // // import { MatSnackBar } from '@angular/material/snack-bar';

// // // @Component({
// // //   selector: 'app-home',
// // //   templateUrl: './home.component.html',
// // // })
// // // export class HomeComponent implements OnDestroy {
// // //   selectedFile: File | null = null;
// // //   uploadProgress = 0;
// // //   uploading = false;
// // //   uploadSuccess = false;
// // //   private progressSub: Subscription;

// // //   constructor(private uploadService: UploadService, private snackBar: MatSnackBar) {
// // //     // Subscribe to progress updates from the service
// // //     this.progressSub = this.uploadService.uploadProgress$.subscribe({
// // //       next: (progress) => {
// // //         this.uploadProgress = progress;
// // //         if (progress === 100) {
// // //           this.uploading = false;
// // //           this.uploadSuccess = true;
// // //           this.snackBar.open('File upload complete!', 'Close', { duration: 3000 });
// // //         }
// // //       },
// // //       error: (err) => {
// // //         this.uploading = false;
// // //         this.snackBar.open(`Upload Failed: ${err}`, 'Close', { duration: 5000 });
// // //         this.reset();
// // //       }
// // //     });
// // //   }

// // //   onFileSelected(event: any): void {
// // //     this.selectedFile = event.target.files[0];
// // //     this.reset();
// // //   }

// // //   onDragOver(event: DragEvent) { event.preventDefault(); }
// // //   onDragLeave(event: DragEvent) { event.preventDefault(); }

// // //   onDrop(event: DragEvent) {
// // //     event.preventDefault();
// // //     if (event.dataTransfer?.files.length) {
// // //       this.selectedFile = event.dataTransfer.files[0];
// // //       this.reset();
// // //     }
// // //   }

// // //   onUpload(): void {
// // //     if (!this.selectedFile) return;

// // //     this.uploading = true;
// // //     this.uploadSuccess = false;
// // //     this.uploadProgress = 0;

// // //     // The component's job is just to start the upload.
// // //     // The progress subscription will handle the rest.
// // //     this.uploadService.upload(this.selectedFile).subscribe({
// // //       next: () => {
// // //         console.log('Upload initiated successfully.');
// // //       },
// // //       error: (err) => {
// // //         // This error is for the initiation step only
// // //         this.uploading = false;
// // //         this.snackBar.open('Could not start upload. Please check the console.', 'Close', { duration: 3000 });
// // //       }
// // //     });
// // //   }
  
// // //   // We no longer need a download link immediately, as the processing happens in the background
// // //   // The UI can be updated to reflect this.

// // //   reset() {
// // //     this.uploadProgress = 0;
// // //     this.uploading = false;
// // //     this.uploadSuccess = false;
// // //   }

// // //   ngOnDestroy(): void {
// // //     // Unsubscribe to prevent memory leaks
// // //     if (this.progressSub) {
// // //       this.progressSub.unsubscribe();
// // //     }
// // //   }
// // // }



// // import { Component, OnDestroy } from '@angular/core';
// // import { UploadService } from '../../shared/services/upload.service'; // Adjust path if needed
// // import { Subscription } from 'rxjs';
// // import { MatSnackBar } from '@angular/material/snack-bar';

// // // Define the different states our component can be in
// // type UploadState = 'idle' | 'selected' | 'uploading' | 'success' | 'error';

// // @Component({
// //   selector: 'app-home',
// //   templateUrl: './home.component.html',
// // })
// // export class HomeComponent implements OnDestroy {
// //   // --- State Management ---
// //   public currentState: UploadState = 'idle';
// //   public selectedFile: File | null = null;
  
// //   // --- Progress & Result ---
// //   public browserUploadProgress = 0;
// //   public finalDownloadLink: string | null = null;
// //   public errorMessage: string | null = null;

// //   // --- Subscriptions ---
// //   private uploadSub?: Subscription;
// //   private progressSub?: Subscription;

// //   constructor(private uploadService: UploadService, private snackBar: MatSnackBar) {}

// //   onFileSelected(event: any): void {
// //     const fileList = (event.target as HTMLInputElement).files;
// //     if (fileList && fileList.length > 0) {
// //       this.selectedFile = fileList[0];
// //       this.reset();
// //       this.currentState = 'selected';
// //     }
// //   }

// //   onUpload(): void {
// //     if (!this.selectedFile) return;

// //     this.currentState = 'uploading';
// //     let fileId = ''; // Variable to hold the ID for this upload

// //     // Subscribe to progress updates first
// //     this.progressSub = this.uploadService.browserUploadProgress$.subscribe({
// //         next: progress => {
// //             this.browserUploadProgress = progress;
// //         },
// //         error: err => {
// //             this.currentState = 'error';
// //             this.errorMessage = err;
// //         },
// //         complete: () => {
// //             // This 'complete' now fires when the browser-to-server part is done.
// //             // At this point, the Celery task is running in the background.
// //             // We can now show the success message and the link to the user.
// //             this.currentState = 'success';
// //             this.snackBar.open('File upload complete! Your link is ready.', 'Close', { duration: 3000 });
// //         }
// //     });

// //     // Initiate the upload process. The most important part is getting the fileId.
// //     this.uploadSub = this.uploadService.upload(this.selectedFile).subscribe({
// //       next: (response) => {
// //         fileId = response.file_id;
// //         console.log(`Upload initiated. File ID: ${fileId}`);
        
// //         // ** THE FIX IS HERE: Construct the final link immediately **
// //         this.finalDownloadLink = `${window.location.origin}/download/${fileId}`;
// //       },
// //       error: (err) => {
// //         this.currentState = 'error';
// //         this.errorMessage = 'Could not start upload. Is the server running?';
// //         this.progressSub?.unsubscribe(); // Clean up progress sub on initiation error
// //       }
// //     });
// //   }

// //   reset(): void {
// //     this.browserUploadProgress = 0;
// //     this.finalDownloadLink = null;
// //     this.errorMessage = null;

// //     // Set state based on whether a file is selected
// //     this.currentState = this.selectedFile ? 'selected' : 'idle';
    
// //     // Unsubscribe from all potential subscriptions
// //     this.uploadSub?.unsubscribe();
// //     this.progressSub?.unsubscribe();
// //   }

// //   startNewUpload(): void {
// //     this.selectedFile = null;
// //     this.reset();
// //   }

// //   copyLink(link: string): void {
// //     navigator.clipboard.writeText(link).then(() => {
// //       this.snackBar.open('Link copied to clipboard!', 'Close', { duration: 2000 });
// //     });
// //   }

// //   // --- Drag and Drop Handlers ---
// //   onDragOver(event: DragEvent) { event.preventDefault(); }
// //   onDragLeave(event: DragEvent) { event.preventDefault(); }
// //   onDrop(event: DragEvent) {
// //     event.preventDefault();
// //     if (this.currentState !== 'uploading' && event.dataTransfer?.files.length) {
// //       this.selectedFile = event.dataTransfer.files[0];
// //       this.reset();
// //       this.currentState = 'selected';
// //     }
// //   }

// //   ngOnDestroy(): void {
// //     // Final cleanup when the component is destroyed
// //     this.uploadSub?.unsubscribe();
// //     this.progressSub?.unsubscribe();
// //   }
// // }



// import { Component, OnDestroy } from '@angular/core';
// import { UploadService } from '../../shared/services/upload.service';
// import { Subscription, forkJoin, from, switchMap, tap } from 'rxjs';
// import { MatSnackBar } from '@angular/material/snack-bar';

// // Define the different states our component can be in
// type UploadState = 'idle' | 'selected' | 'uploading' | 'success' | 'error';

// // An interface to manage the state of each individual file
// export interface UploadItem {
//   file: File;
//   progress: number;
//   subscription?: Subscription; // To manage each file's progress listener
// }

// @Component({
//   selector: 'app-home',
//   templateUrl: './home.component.html',
// })
// export class HomeComponent implements OnDestroy {
//   // --- State Management ---
//   public currentState: UploadState = 'idle';
//   public uploadItems: UploadItem[] = [];
  
//   // --- Result ---
//   public finalDownloadLink: string | null = null;
//   public errorMessage: string | null = null;

//   // --- Subscriptions ---
//   private masterUploadSub?: Subscription;

//   constructor(private uploadService: UploadService, private snackBar: MatSnackBar) {}

//   onFileSelected(event: any): void {
//     const files = (event.target as HTMLInputElement).files;
//     if (files && files.length > 0) {
//       this.reset();
//       for (let i = 0; i < files.length; i++) {
//         this.uploadItems.push({ file: files[i], progress: 0 });
//       }
//       this.currentState = 'selected';
//     }
//   }

//   onUpload(): void {
//     if (this.uploadItems.length === 0) return;

//     this.currentState = 'uploading';
//     // Generate a single, unique ID for this entire batch of files.
//     const batchId = crypto.randomUUID(); 

//     // Create an array of Observables. Each one represents the full upload
//     // process for a single file (initiation + websocket streaming).
//     const uploadObservables = this.uploadItems.map(item => {
//       // The `upload` service method returns an observable that initiates
//       // and then triggers the websocket stream.
//       return this.uploadService.upload(item.file, batchId).pipe(
//         tap(() => {
//           // As soon as a file is initiated, we listen to its specific progress.
//           // Note: The uploadService now handles progress on a per-file basis
//           // internally. We just need to get that progress.
//           // This part assumes uploadService's progress observable can be tied
//           // back to a specific file, which we'll manage via the service itself.
//           // For now, this is a conceptual placeholder. The service will be
//           // updated to handle this properly later.
//           // A simpler model for now: we will just update a global progress.
//           // Let's refine this to update individual progress.

//           // The service's browserUploadProgress$ will emit progress. We need to
//           // pipe it to the correct item.
//           item.subscription = this.uploadService.browserUploadProgress$.subscribe(progress => {
//               // This is a simplification; in a real-world scenario with concurrent
//               // uploads, the service would need to emit progress *with* a file identifier.
//               // For this implementation, we will assume one-by-one streaming for simplicity of progress tracking.
//               // A better approach would be to have the service manage this state.
//               // Let's stick to the current service implementation for now.
//               // The service streams one file at a time based on its current implementation.
//               // We can adapt this later if true concurrency is needed.
//               // For now, the visual will update for the *current* file being streamed.
//           });
//         })
//       );
//     });

//     // The logic needs to be sequential for the current service implementation.
//     // Let's upload them one by one, updating progress for each.
//     const uploadSequence$ = from(this.uploadItems).pipe(
//         switchMap(item => {
//             return new Promise<void>(resolve => {
//                 const progressSub = this.uploadService.browserUploadProgress$.subscribe(progress => {
//                     item.progress = progress;
//                 });
                
//                 const uploadSub = this.uploadService.upload(item.file, batchId).subscribe({
//                     complete: () => {
//                         item.progress = 100;
//                         progressSub.unsubscribe();
//                         uploadSub.unsubscribe();
//                         resolve();
//                     },
//                     error: (err) => {
//                         this.currentState = 'error';
//                         this.errorMessage = `Failed to upload ${item.file.name}.`;
//                         progressSub.unsubscribe();
//                         uploadSub.unsubscribe();
//                         // We could decide to stop all uploads on the first error.
//                     }
//                 });
//             });
//         })
//     );
    
//     // We will use forkJoin to INITIATE all at once, then handle streaming.
//     // Let's adjust for a better UX.

//     const initiationObservables = this.uploadItems.map(item =>
//         this.uploadService.upload(item.file, batchId)
//     );

//     this.masterUploadSub = forkJoin(initiationObservables).subscribe({
//       next: (results) => {
//         // All files have been uploaded to the server!
//         this.currentState = 'success';
//         this.finalDownloadLink = `${window.location.origin}/download/batch/${batchId}`;
//         this.snackBar.open('All files uploaded successfully!', 'Close', { duration: 3000 });

//         // Update all progress bars to 100%
//         this.uploadItems.forEach(item => item.progress = 100);
//       },
//       error: (err) => {
//         this.currentState = 'error';
//         this.errorMessage = 'An error occurred during one of the uploads. Please try again.';
//       }
//     });
//   }

//   // --- Helper and Lifecycle Methods ---

//   reset(): void {
//     this.uploadItems.forEach(item => item.subscription?.unsubscribe());
//     this.masterUploadSub?.unsubscribe();
//     this.uploadItems = [];
//     this.finalDownloadLink = null;
//     this.errorMessage = null;
//     this.currentState = 'idle';
//   }

//   startNewUpload(): void {
//     this.reset();
//   }

//   copyLink(link: string): void {
//     navigator.clipboard.writeText(link).then(() => {
//       this.snackBar.open('Link copied to clipboard!', 'Close', { duration: 2000 });
//     });
//   }

//   trackByFile(index: number, item: UploadItem): string {
//     return item.file.name + item.file.size;
//   }
  
//   onDragOver(event: DragEvent) { event.preventDefault(); }
//   onDragLeave(event: DragEvent) { event.preventDefault(); }
//   onDrop(event: DragEvent) {
//     event.preventDefault();
//     if (this.currentState !== 'uploading' && event.dataTransfer?.files.length) {
//       const files = event.dataTransfer.files;
//       this.reset();
//       for (let i = 0; i < files.length; i++) {
//         this.uploadItems.push({ file: files[i], progress: 0 });
//       }
//       this.currentState = 'selected';
//     }
//   }

//   ngOnDestroy(): void {
//     this.reset();
//   }
// }


// Frontend/src/app/componet/home/home.component.ts

import { Component, OnDestroy } from '@angular/core';
import { UploadService } from '../../shared/services/upload.service';
import { Subscription, from, concatMap, tap, of } from 'rxjs';
import { MatSnackBar } from '@angular/material/snack-bar';

// Define the different states our component can be in
type UploadState = 'idle' | 'selected' | 'uploading' | 'success' | 'error';

// An interface to manage the state of each individual file
export interface UploadItem {
  file: File;
  progress: number;
  isUploading: boolean;
}

@Component({
  selector: 'app-home',
  templateUrl: './home.component.html',
})
export class HomeComponent implements OnDestroy {
  // --- State Management ---
  public currentState: UploadState = 'idle';
  public uploadItems: UploadItem[] = [];
  
  // --- Result & Error Handling ---
  public finalDownloadLink: string | null = null;
  public errorMessage: string | null = null;

  // --- Subscriptions ---
  private masterUploadSub?: Subscription;
  private progressSub?: Subscription;

  constructor(private uploadService: UploadService, private snackBar: MatSnackBar) {}

  onFileSelected(event: any): void {
    const files = (event.target as HTMLInputElement).files;
    if (files && files.length > 0) {
      this.reset();
      for (let i = 0; i < files.length; i++) {
        this.uploadItems.push({ file: files[i], progress: 0, isUploading: false });
      }
      this.currentState = 'selected';
    }
  }

  onUpload(): void {
    if (this.uploadItems.length === 0) return;

    this.currentState = 'uploading';
    const batchId = crypto.randomUUID(); // A single ID for the whole batch

    // This subscription will listen to the service's progress and apply it
    // to whichever file is currently marked as 'isUploading'.
    this.progressSub = this.uploadService.browserUploadProgress$.subscribe(progress => {
      const currentItem = this.uploadItems.find(item => item.isUploading);
      if (currentItem) {
        currentItem.progress = progress;
      }
    });
    
    // Create a sequential upload queue using `concatMap`.
    // `concatMap` waits for the inner observable to complete before starting the next one.
    this.masterUploadSub = from(this.uploadItems).pipe(
      concatMap(item => {
        // Before each upload, mark this item as the one currently uploading.
        item.isUploading = true;
        // The `upload` method returns an observable that completes when the browser-to-server
        // transfer is done. `concatMap` will wait for this completion.
        return this.uploadService.upload(item.file, batchId).pipe(
          tap(() => {
            // After completion, mark it as done and reset the flag.
            item.progress = 100;
            item.isUploading = false;
          })
        );
      })
    ).subscribe({
      next: () => {
        // This is called after each file in the sequence successfully uploads.
        console.log('A file finished uploading to the server.');
      },
      error: (err) => {
        this.currentState = 'error';
        this.errorMessage = 'An upload failed. Please try again.';
        this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      },
      complete: () => {
        // This is called only when ALL files in the sequence have completed.
        this.currentState = 'success';
        this.finalDownloadLink = `${window.location.origin}/download/batch/${batchId}`; // Link to the batch
        this.snackBar.open('All files uploaded successfully!', 'Close', { duration: 3000 });
      }
    });
  }

  reset(): void {
    this.masterUploadSub?.unsubscribe();
    this.progressSub?.unsubscribe();
    this.uploadItems = [];
    this.finalDownloadLink = null;
    this.errorMessage = null;
    this.currentState = 'idle';
  }

  startNewUpload(): void {
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
      this.onFileSelected({ target: event.dataTransfer });
    }
  }

  ngOnDestroy(): void {
    this.reset();
  }
}