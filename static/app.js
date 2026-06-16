// DOM Elements
const searchForm = document.getElementById('search-form');
const urlInput = document.getElementById('youtube-url');
const btnFetch = document.getElementById('btn-fetch');
const btnText = document.getElementById('btn-text');
const fetchSpinner = document.getElementById('fetch-spinner');
const errorAlert = document.getElementById('error-alert');

const videoDetailsContainer = document.getElementById('video-details-container');
const videoThumbnail = document.getElementById('video-thumbnail');
const videoDuration = document.getElementById('video-duration');
const videoTitle = document.getElementById('video-title');
const videoUploader = document.getElementById('video-uploader');
const videoViews = document.getElementById('video-views');

const combinedList = document.getElementById('combined-list');
const videoOnlyList = document.getElementById('video_only-list');
const audioOnlyList = document.getElementById('audio_only-list');

const downloadModal = document.getElementById('download-modal');
const statusText = document.getElementById('status-text');

// Active video URL context
let activeUrl = "";

// Initialize Event Listeners
searchForm.addEventListener('submit', handleFetchVideo);

// Format Helper: Comma separate numbers
function formatViews(num) {
    if (!num) return "0 views";
    return parseInt(num).toLocaleString() + " views";
}

// Show/Hide Helpers
function showError(msg) {
    errorAlert.textContent = msg;
    errorAlert.style.display = 'block';
    setTimeout(() => {
        errorAlert.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 100);
}

function hideError() {
    errorAlert.style.display = 'none';
}

function showLoading(loading) {
    if (loading) {
        btnFetch.disabled = true;
        fetchSpinner.style.display = 'inline-block';
        btnText.textContent = "Analyzing...";
    } else {
        btnFetch.disabled = false;
        fetchSpinner.style.display = 'none';
        btnText.textContent = "Analyze Link";
    }
}

function showModal(statusMsg) {
    statusText.textContent = statusMsg;
    downloadModal.style.display = 'flex';
}

function updateModalStatus(statusMsg) {
    statusText.textContent = statusMsg;
}

function hideModal() {
    downloadModal.style.display = 'none';
}

// Fetch Video Info
async function handleFetchVideo(e) {
    e.preventDefault();
    hideError();
    videoDetailsContainer.style.display = 'none';
    
    const url = urlInput.value.trim();
    if (!url) return;
    
    showLoading(true);
    
    try {
        const response = await fetch(`/api/info?url=${encodeURIComponent(url)}`);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || "Failed to analyze link.");
        }
        
        activeUrl = url;
        renderVideoInfo(data);
    } catch (err) {
        showError(err.message);
    } finally {
        showLoading(false);
    }
}

// Render video metadata and available formats
function renderVideoInfo(data) {
    videoThumbnail.src = data.thumbnail || "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=640";
    videoDuration.textContent = data.duration_str;
    videoTitle.textContent = data.title;
    videoUploader.textContent = data.uploader || "Unknown Uploader";
    videoViews.textContent = formatViews(data.view_count);
    
    // Clear format lists
    combinedList.innerHTML = "";
    videoOnlyList.innerHTML = "";
    audioOnlyList.innerHTML = "";
    
    const formats = data.formats;
    
    // 1. Combined formats (Video + Audio)
    if (formats.combined && formats.combined.length > 0) {
        formats.combined.forEach(f => {
            combinedList.appendChild(createFormatCard(f, "Video + Audio"));
        });
    } else {
        combinedList.innerHTML = `<p style="grid-column: 1/-1; text-align: center; color: var(--text-dim);">No pre-merged formats found. Download from 'Video Only' or 'Audio Only' instead.</p>`;
    }
    
    // 2. Video Only formats
    if (formats.video_only && formats.video_only.length > 0) {
        formats.video_only.forEach(f => {
            videoOnlyList.appendChild(createFormatCard(f, "Video Only"));
        });
    } else {
        videoOnlyList.innerHTML = `<p style="grid-column: 1/-1; text-align: center; color: var(--text-dim);">No video-only formats available.</p>`;
    }
    
    // 3. Audio Only formats
    if (formats.audio_only && formats.audio_only.length > 0) {
        formats.audio_only.forEach(f => {
            // Display bitrate for audio (e.g. 128kbps) if available
            const note = f.abr ? `${f.abr}kbps` : '';
            audioOnlyList.appendChild(createFormatCard(f, "Audio Only", note));
        });
    } else {
        audioOnlyList.innerHTML = `<p style="grid-column: 1/-1; text-align: center; color: var(--text-dim);">No audio formats available.</p>`;
    }
    
    // Switch to first tab default
    switchTab('combined');
    
    // Show container
    videoDetailsContainer.style.display = 'block';
    setTimeout(() => {
        videoDetailsContainer.scrollIntoView({ behavior: 'smooth' });
    }, 100);
}

// Create Card Element for single Format
function createFormatCard(f, type, extraNote = "") {
    const card = document.createElement('div');
    card.className = "format-item";
    
    // Info display
    let label = f.resolution;
    if (f.fps) label += ` (${f.fps}fps)`;
    if (extraNote) label += ` - ${extraNote}`;
    else if (f.note) label += ` (${f.note})`;
    
    card.innerHTML = `
        <div class="format-quality">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--primary);"><circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/></svg>
            <span>${label}</span>
        </div>
        <div style="display: flex; justify-content: center;">
            <span class="format-ext">${f.ext}</span>
        </div>
        <div class="format-size">${f.filesize_str}</div>
        <div>
            <button class="btn-download" onclick="triggerDownload('${f.format_id}')">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>
                Download
            </button>
        </div>
    `;
    
    return card;
}

// Switch Tabs
window.switchTab = function(tabId) {
    // Update active tab button
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        if (btn.getAttribute('onclick').includes(tabId)) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
    
    // Update active tab panel
    const panels = document.querySelectorAll('.tab-panel');
    panels.forEach(panel => {
        if (panel.id === `tab-${tabId}`) {
            panel.classList.add('active');
        } else {
            panel.classList.remove('active');
        }
    });
};

// Trigger download request
window.triggerDownload = async function(formatId) {
    if (!activeUrl) return;
    
    showModal("Downloading video onto server...");
    
    try {
        const downloadUrl = `/api/download?url=${encodeURIComponent(activeUrl)}&format_id=${encodeURIComponent(formatId)}`;
        const response = await fetch(downloadUrl);
        
        if (!response.ok) {
            // Read error response body as JSON
            const data = await response.json();
            throw new Error(data.detail || "Server failed to process the download.");
        }
        
        updateModalStatus("Streaming file to browser...");
        
        const blob = await response.blob();
        
        // Extract filename from response headers
        let filename = `downloaded_video_${formatId}`;
        const disposition = response.headers.get('content-disposition');
        if (disposition && disposition.indexOf('attachment') !== -1) {
            const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
            const matches = filenameRegex.exec(disposition);
            if (matches != null && matches[1]) { 
                filename = matches[1].replace(/['"]/g, '');
            }
        }
        
        // Trigger download in browser
        const downloadBlobUrl = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = downloadBlobUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        
        // Cleanup resources
        window.URL.revokeObjectURL(downloadBlobUrl);
    } catch (err) {
        showError(err.message);
    } finally {
        hideModal();
    }
};
