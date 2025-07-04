// // frontend/src/app/services/file.service.ts (Completely Updated)

// import { Injectable } from '@angular/core';
// import { HttpClient, HttpEventType, HttpHeaders, HttpRequest } from '@angular/common/http';
// import { Observable, Subject, switchMap, tap } from 'rxjs';

// const API_URL = 'http://localhost:8000/api/v1';

// @Injectable({
//   providedIn: 'root'
// })
// export class FileService {
//   [x: string]: any;

//   private apiUrl = 'http://localhost:5000/api/v1';
//   constructor(private http: HttpClient) { }

//   // --- THE NEW UPLOAD METHOD ---
//   upload(file: File): Observable<any> {
//     const progressSubject = new Subject<number>();
//     let fileId = '';
    
//     // Step 1: Initiate the upload with our backend
//     const initiate$ = this.http.post<{file_id: string, upload_url: string}>(`${API_URL}/upload/initiate`, {
//       filename: file.name,
//       filesize: file.size,
//       content_type: file.type || 'application/octet-stream'
//     });

//     return initiate$.pipe(
//       switchMap(response => {
//         fileId = response.file_id;
//         const uploadUrl = response.upload_url;
        
//         // Step 2: Upload the file directly to Google Drive's URL
//         const uploadReq = new HttpRequest('PUT', uploadUrl, file, {
//           reportProgress: true,
//         });

//         return this.http.request(uploadReq);
//       }),
//       switchMap(event => {
//         if (event.type === HttpEventType.UploadProgress) {
//           const percentDone = Math.round(100 * event.loaded / event.total!);
//           progressSubject.next(percentDone);
//           // Return an observable that emits progress but doesn't complete the stream
//           return new Observable(sub => {});
//         } else if (event.type === HttpEventType.Response) {
//           // Step 3: Finalize the upload with our backend
//           return this.http.post(`${API_URL}/upload/finalize/${fileId}`, {});
//         }
//         // For other event types, do nothing and wait
//         return new Observable(sub => {});
//       })
//     );
//   }

//   // --- Other methods remain the same ---
//   getFileMeta(id: string): Observable<any> {
//     return this.http.get<any>(`${this.apiUrl}/files/${id}/meta`);
//   }

//   getStreamUrl(id: string): string {
//     return `${this.apiUrl}/download/stream/${id}`;
//   }

//   getUserFiles(): Observable<any> {
//     // This already works with the AuthInterceptor
//     return this.http.get(`${API_URL}/files/me/history`);
//   }
// }

// frontend/src/app/services/file.service.ts (Corrected)

// import { Injectable } from '@angular/core';
// import { HttpClient, HttpEventType, HttpHeaders, HttpRequest } from '@angular/common/http';
// import { Observable, Subject, switchMap, tap } from 'rxjs';

// // Note: The original file had two different API_URL constants. I've consolidated them.
// const API_URL = 'http://localhost:5000/api/v1';

// @Injectable({
//   providedIn: 'root'
// })
// export class FileService {
//   // THIS LINE WAS REMOVED: [x: string]: any;

//   private apiUrl = API_URL; // Using the consolidated constant
//   constructor(private http: HttpClient) { }

//   // --- THIS METHOD IS FROM THE ORIGINAL FILE, IT WILL BE UNUSED BUT WE LEAVE IT FOR NOW ---
//   upload(file: File): Observable<any> {
//     const progressSubject = new Subject<number>();
//     let fileId = '';
    
//     const initiate$ = this.http.post<{file_id: string, upload_url: string}>(`${this.apiUrl}/upload/initiate`, {
//       filename: file.name,
//       filesize: file.size,
//       content_type: file.type || 'application/octet-stream'
//     });

//     return initiate$.pipe(
//       switchMap(response => {
//         fileId = response.file_id;
//         const uploadUrl = response.upload_url;
        
//         const uploadReq = new HttpRequest('PUT', uploadUrl, file, {
//           reportProgress: true,
//         });

//         return this.http.request(uploadReq);
//       }),
//       switchMap(event => {
//         if (event.type === HttpEventType.UploadProgress) {
//           const percentDone = Math.round(100 * event.loaded / event.total!);
//           progressSubject.next(percentDone);
//           return new Observable(sub => {});
//         } else if (event.type === HttpEventType.Response) {
//           return this.http.post(`${this.apiUrl}/upload/finalize/${fileId}`, {});
//         }
//         return new Observable(sub => {});
//       })
//     );
//   }

//   // --- Methods used by DownloadComponent ---
//   getFileMeta(id: string): Observable<any> {
//     return this.http.get<any>(`${this.apiUrl}/files/${id}/meta`);
//   }

//   getStreamUrl(id: string): string {
//     return `${this.apiUrl}/download/stream/${id}`;
//   }

//   getBatchMeta(batchId: string): Observable<any[]> {
//     return this.http.get<any[]>(`${this.apiUrl}/batch/${batchId}`);
//   }

//   getUserFiles(): Observable<any> {
//     // This already works with the AuthInterceptor
//     return this.http.get(`${this.apiUrl}/files/me/history`);
//   }
// }



// Frontend/src/app/shared/services/file.service.ts (Corrected)

import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class FileService {

  private apiUrl = environment.apiUrl; // Use the environment variable

  constructor(private http: HttpClient) { }

  // Fetches metadata for a single file or a batch
  getFileMeta(id: string): Observable<any> {
    // Note: You might need a separate endpoint for batch IDs later.
    // For now, this assumes single file meta.
    return this.http.get<any>(`${this.apiUrl}/files/${id}/meta`);
  }

  // Gets the direct download URL for a single file
  getStreamUrl(id: string): string {
    return `${this.apiUrl}/download/stream/${id}`;
  }

  // Gets the file history for the logged-in user
  getUserFiles(): Observable<any> {
    return this.http.get(`${this.apiUrl}/files/me/history`);
  }
}