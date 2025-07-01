import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { FileService } from '../../shared/services/file.service';
import { Observable } from 'rxjs';

@Component({
  selector: 'app-download',
  templateUrl: './download.component.html',
})
export class DownloadComponent implements OnInit {
  
  public fileMeta$!: Observable<any>;
  public downloadUrl: string | null = null;
  private fileId: string | null = null;

  constructor(
    private route: ActivatedRoute,
    private fileService: FileService
  ) {}

  ngOnInit(): void {
    // Get the 'id' parameter from the URL
    this.fileId = this.route.snapshot.paramMap.get('id');

    if (this.fileId) {
      // Fetch the file metadata from our backend
      this.fileMeta$ = this.fileService.getFileMeta(this.fileId);
      // Construct the direct download stream URL
      this.downloadUrl = this.fileService.getStreamUrl(this.fileId);
    }
  }
}