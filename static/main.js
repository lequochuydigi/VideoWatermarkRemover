// State variables
let videos = [];
let selectedVideo = null;
let originalWidth = 1280;
let originalHeight = 720;
let cropBox = { x: 0, y: 0, width: 0, height: 0 };
let isDrawing = false;
let startX = 0;
let startY = 0;
let pollInterval = null;

// Shape state
let currentShape = 'rect';        // rect | diamond | ellipse | poly
let lassoPoints = [];             // canvas-buffer coords while drawing
let lassoOrigPoints = [];         // original video coords sent to backend

// Zoom / pan state
let zoomLevel = 1;
let panX = 0, panY = 0;
let isPanning = false;
let spaceDown = false;
let panStartX = 0, panStartY = 0;
let panOriginX = 0, panOriginY = 0;

// DOM Elements
const videoList = document.getElementById('video-list');
const settingsGroup = document.getElementById('settings-group');
const canvasPlaceholder = document.getElementById('canvas-placeholder');
const interactiveContainer = document.getElementById('interactive-container');
const previewImage = document.getElementById('preview-image');
const selectionCanvas = document.getElementById('selection-canvas');
const coordDisplay = document.getElementById('coord-display');
const btnProcess = document.getElementById('btn-process');
const btnDetect = document.getElementById('btn-detect');
const detectStatus = document.getElementById('detect-status');
const canvasHint = document.getElementById('canvas-hint');

const btnPreview = document.getElementById('btn-preview');
const smartSettings = document.getElementById('smart-settings');
const inpaintSettings = document.getElementById('inpaint-settings');
const blurSettings = document.getElementById('blur-settings');

// Before/After preview
const baPreview = document.getElementById('ba-preview');
const baLoading = document.getElementById('ba-loading');
const baBefore = document.getElementById('ba-before');
const baAfter = document.getElementById('ba-after');
const baStats = document.getElementById('ba-stats');

// Sliders (id -> value-label id)
const SLIDERS = {
    gain: 'val-gain', floor: 'val-floor', edge: 'val-edge',
    tophat: 'val-tophat', despill: 'val-despill', edge_blur: 'val-edge_blur',
    radius: 'val-radius', blur: 'val-blur'
};
let previewTimer = null;

// Zoom controls
const zoomControls = document.getElementById('zoom-controls');
const zoomLevelLabel = document.getElementById('zoom-level');
const btnZoomIn = document.getElementById('btn-zoom-in');
const btnZoomOut = document.getElementById('btn-zoom-out');
const btnZoomReset = document.getElementById('btn-zoom-reset');

// Modals
const progressModalEl = document.getElementById('progress-modal');
const progressBarFill = document.getElementById('progress-bar-fill');
const progressText = document.getElementById('progress-text');
const progressVideoName = document.getElementById('progress-video-name');

const resultModalEl = document.getElementById('result-modal');
const resultFilepath = document.getElementById('result-filepath');
const btnCloseResult = document.getElementById('btn-close-result');

// Context for Canvas
const ctx = selectionCanvas.getContext('2d');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadVideos();
    setupCanvasListeners();
    setupPresetListeners();
    setupShapeListeners();
    setupZoomListeners();

    btnDetect.addEventListener('click', runAutoDetection);
    btnProcess.addEventListener('click', startProcessing);
    if (btnPreview) btnPreview.addEventListener('click', () => runPreview(false));

    btnCloseResult.addEventListener('click', () => {
        resultModalEl.classList.add('hidden');
    });

    setupSliders();
    document.querySelectorAll('input[name="method"]').forEach(radio => {
        radio.addEventListener('change', updateMethodUI);
    });
    updateMethodUI();
});

// Show the slider group for the selected method
function updateMethodUI() {
    const method = document.querySelector('input[name="method"]:checked').value;
    smartSettings.style.display = method === 'smart' ? 'block' : 'none';
    inpaintSettings.style.display = method === 'inpaint' ? 'block' : 'none';
    blurSettings.style.display = method === 'blur' ? 'block' : 'none';
    // Re-render preview for the new method if a region is already selected
    if (!btnProcess.disabled) schedulePreview();
}

// Wire all sliders: update their value label and schedule a live preview
function setupSliders() {
    Object.entries(SLIDERS).forEach(([id, labelId]) => {
        const el = document.getElementById('sld-' + id);
        const lbl = document.getElementById(labelId);
        if (!el) return;
        el.addEventListener('input', () => {
            lbl.innerText = el.value;
            schedulePreview();
        });
    });
}

function schedulePreview() {
    if (btnProcess.disabled || !selectedVideo) return;
    if (previewTimer) clearTimeout(previewTimer);
    previewTimer = setTimeout(() => runPreview(true), 450);
}

function collectParams() {
    const v = (id) => parseFloat(document.getElementById('sld-' + id).value);
    return {
        gain: v('gain'), floor: v('floor'),
        edge: parseInt(document.getElementById('sld-edge').value, 10),
        tophat: parseInt(document.getElementById('sld-tophat').value, 10),
        despill: v('despill'),
        edge_blur: parseInt(document.getElementById('sld-edge_blur').value, 10),
        radius: parseInt(document.getElementById('sld-radius').value, 10),
        blur: parseInt(document.getElementById('sld-blur').value, 10)
    };
}

// Load videos list from API
async function loadVideos() {
    try {
        const res = await fetch('/api/videos');
        const data = await res.json();
        if (data.success) {
            videos = data.videos;
            renderVideoList();
        } else {
            videoList.innerHTML = `<li class="loading-item text-danger">Lỗi: ${data.error}</li>`;
        }
    } catch (err) {
        videoList.innerHTML = `<li class="loading-item text-danger">Lỗi kết nối tới server</li>`;
    }
}

// Render list of videos in left panel
function renderVideoList() {
    if (videos.length === 0) {
        videoList.innerHTML = '<li class="loading-item">Không tìm thấy video nào trong thư mục Downloads</li>';
        return;
    }

    videoList.innerHTML = '';
    videos.forEach(video => {
        const li = document.createElement('li');
        li.dataset.name = video.name;

        const sizeMb = (video.size / (1024 * 1024)).toFixed(1);

        li.innerHTML = `
            <span class="video-name">${video.name}</span>
            <div class="video-meta">
                <span><i class="fa-solid fa-file-video"></i> ${sizeMb} MB</span>
                <span><i class="fa-solid fa-clock"></i> ${new Date(video.mtime * 1000).toLocaleDateString()}</span>
            </div>
        `;

        li.addEventListener('click', () => selectVideo(video.name, li));
        videoList.appendChild(li);
    });
}

// Select video and fetch frame preview
async function selectVideo(videoName, element) {
    document.querySelectorAll('.video-list li').forEach(el => el.classList.remove('active'));
    element.classList.add('active');

    selectedVideo = videoName;

    canvasPlaceholder.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i><p>Đang trích xuất khung hình từ ${videoName}...</p>`;
    canvasPlaceholder.classList.remove('hidden');
    interactiveContainer.classList.add('hidden');
    zoomControls.classList.add('hidden');
    settingsGroup.classList.add('disabled');
    btnProcess.disabled = true;

    // Reset selection + zoom
    resetSelection();
    resetZoom();
    if (baPreview) baPreview.classList.add('hidden');
    if (btnPreview) btnPreview.disabled = true;

    try {
        const res = await fetch('/api/extract_frame', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video_name: videoName })
        });
        const data = await res.json();

        if (data.success) {
            originalWidth = data.width;
            originalHeight = data.height;

            previewImage.src = data.preview_url + "?t=" + new Date().getTime();

            previewImage.onload = () => {
                canvasPlaceholder.classList.add('hidden');
                interactiveContainer.classList.remove('hidden');
                zoomControls.classList.remove('hidden');
                settingsGroup.classList.remove('disabled');
                resizeCanvas();
            };
        } else {
            canvasPlaceholder.innerHTML = `<i class="fa-solid fa-triangle-exclamation text-danger"></i><p>Lỗi: ${data.error}</p>`;
        }
    } catch (err) {
        canvasPlaceholder.innerHTML = `<i class="fa-solid fa-triangle-exclamation text-danger"></i><p>Lỗi kết nối tới server</p>`;
    }
}

function resetSelection() {
    cropBox = { x: 0, y: 0, width: 0, height: 0 };
    lassoPoints = [];
    lassoOrigPoints = [];
    updateCoordDisplay();
    drawSelection();
}

// Adjust canvas buffer to match the displayed (unscaled) image dimensions
function resizeCanvas() {
    if (!interactiveContainer.classList.contains('hidden')) {
        selectionCanvas.width = previewImage.clientWidth;
        selectionCanvas.height = previewImage.clientHeight;
        drawSelection();
    }
}

window.addEventListener('resize', resizeCanvas);

// ---- Zoom & Pan ---------------------------------------------------------
function applyTransform() {
    interactiveContainer.style.transform =
        `scale(${zoomLevel}) translate(${panX}px, ${panY}px)`;
    zoomLevelLabel.innerText = Math.round(zoomLevel * 100) + '%';
}

function resetZoom() {
    zoomLevel = 1; panX = 0; panY = 0;
    applyTransform();
}

function setZoom(z) {
    zoomLevel = Math.max(1, Math.min(5, z));
    if (zoomLevel === 1) { panX = 0; panY = 0; }
    applyTransform();
}

function setupZoomListeners() {
    btnZoomIn.addEventListener('click', () => setZoom(zoomLevel + 0.5));
    btnZoomOut.addEventListener('click', () => setZoom(zoomLevel - 0.5));
    btnZoomReset.addEventListener('click', resetZoom);

    // Space toggles pan mode
    window.addEventListener('keydown', (e) => {
        if (e.code === 'Space' && !spaceDown) {
            spaceDown = true;
            if (zoomLevel > 1) selectionCanvas.style.cursor = 'grab';
            // prevent page scroll when over the canvas
            if (document.activeElement === document.body) e.preventDefault();
        }
    });
    window.addEventListener('keyup', (e) => {
        if (e.code === 'Space') {
            spaceDown = false;
            isPanning = false;
            selectionCanvas.style.cursor = 'crosshair';
        }
    });
}

// Map a mouse event to canvas-buffer coordinates (handles zoom via rect size).
function getCanvasPoint(e) {
    const rect = selectionCanvas.getBoundingClientRect();
    const sx = selectionCanvas.width / rect.width;
    const sy = selectionCanvas.height / rect.height;
    return {
        x: (e.clientX - rect.left) * sx,
        y: (e.clientY - rect.top) * sy
    };
}

// Setup mouse drawing listeners on canvas
function setupCanvasListeners() {
    selectionCanvas.addEventListener('mousedown', (e) => {
        if (!selectedVideo) return;

        // Pan mode (Space held + zoomed in)
        if (spaceDown && zoomLevel > 1) {
            isPanning = true;
            panStartX = e.clientX; panStartY = e.clientY;
            panOriginX = panX; panOriginY = panY;
            selectionCanvas.style.cursor = 'grabbing';
            return;
        }

        isDrawing = true;
        const p = getCanvasPoint(e);
        startX = p.x; startY = p.y;

        if (currentShape === 'poly') {
            lassoPoints = [{ x: startX, y: startY }];
        } else {
            cropBox = { x: startX, y: startY, width: 0, height: 0 };
        }
    });

    selectionCanvas.addEventListener('mousemove', (e) => {
        if (isPanning) {
            // Translate is applied before scale, so divide delta by zoom.
            panX = panOriginX + (e.clientX - panStartX) / zoomLevel;
            panY = panOriginY + (e.clientY - panStartY) / zoomLevel;
            applyTransform();
            return;
        }
        if (!isDrawing) return;
        const p = getCanvasPoint(e);

        if (currentShape === 'poly') {
            lassoPoints.push({ x: p.x, y: p.y });
            drawSelection();
        } else {
            const x = Math.min(startX, p.x);
            const y = Math.min(startY, p.y);
            const width = Math.abs(startX - p.x);
            const height = Math.abs(startY - p.y);
            cropBox = { x, y, width, height };
            drawSelection();
            updateCoordDisplay();
        }
    });

    selectionCanvas.addEventListener('mouseup', () => {
        if (isPanning) {
            isPanning = false;
            selectionCanvas.style.cursor = spaceDown ? 'grab' : 'crosshair';
            return;
        }
        if (!isDrawing) return;
        isDrawing = false;

        if (currentShape === 'poly') {
            finalizeLasso();
        } else {
            convertToOriginalCoords();
            if (cropBox.width > 2 && cropBox.height > 2) {
                enableActions();
            } else {
                disableActions("Chưa chọn (Kích thước quá bé)");
            }
        }
    });
}

function finalizeLasso() {
    if (lassoPoints.length < 3) {
        disableActions("Chưa chọn (Vẽ ít nhất 3 điểm)");
        lassoPoints = [];
        drawSelection();
        return;
    }
    // bbox of lasso in canvas coords
    const xs = lassoPoints.map(p => p.x);
    const ys = lassoPoints.map(p => p.y);
    cropBox.x = Math.min(...xs);
    cropBox.y = Math.min(...ys);
    cropBox.width = Math.max(...xs) - cropBox.x;
    cropBox.height = Math.max(...ys) - cropBox.y;

    // convert bbox + all points to original coords
    convertToOriginalCoords();
    const scaleX = originalWidth / selectionCanvas.width;
    const scaleY = originalHeight / selectionCanvas.height;
    lassoOrigPoints = lassoPoints.map(p => [
        Math.round(p.x * scaleX), Math.round(p.y * scaleY)
    ]);

    drawSelection();
    updateCoordDisplay();
    if (cropBox.width > 2 && cropBox.height > 2) enableActions();
    else disableActions("Chưa chọn (Vùng quá bé)");
}

function enableActions() {
    btnProcess.disabled = false;
    if (btnPreview) btnPreview.disabled = false;
    schedulePreview();
}
function disableActions(msg) {
    btnProcess.disabled = true;
    if (btnPreview) btnPreview.disabled = true;
    if (msg) coordDisplay.innerText = msg;
}

// Convert drawn bbox (canvas-buffer coords) to original video dimensions
function convertToOriginalCoords() {
    const scaleX = originalWidth / selectionCanvas.width;
    const scaleY = originalHeight / selectionCanvas.height;

    cropBox.origX = Math.round(cropBox.x * scaleX);
    cropBox.origY = Math.round(cropBox.y * scaleY);
    cropBox.origWidth = Math.round(cropBox.width * scaleX);
    cropBox.origHeight = Math.round(cropBox.height * scaleY);
}

// Draw the selection (shape-aware)
function drawSelection() {
    ctx.clearRect(0, 0, selectionCanvas.width, selectionCanvas.height);

    const fill = 'rgba(139, 92, 246, 0.3)';
    const stroke = '#8b5cf6';
    ctx.fillStyle = fill;
    ctx.strokeStyle = stroke;
    ctx.lineWidth = 2;

    if (currentShape === 'poly') {
        if (lassoPoints.length >= 2) {
            ctx.beginPath();
            ctx.moveTo(lassoPoints[0].x, lassoPoints[0].y);
            for (let i = 1; i < lassoPoints.length; i++) {
                ctx.lineTo(lassoPoints[i].x, lassoPoints[i].y);
            }
            ctx.closePath();
            ctx.fill();
            ctx.stroke();
        }
        return;
    }

    if (cropBox.width > 0 && cropBox.height > 0) {
        const { x, y, width, height } = cropBox;
        if (currentShape === 'diamond') {
            const cx = x + width / 2, cy = y + height / 2;
            ctx.beginPath();
            ctx.moveTo(cx, y);
            ctx.lineTo(x + width, cy);
            ctx.lineTo(cx, y + height);
            ctx.lineTo(x, cy);
            ctx.closePath();
            ctx.fill();
            ctx.stroke();
        } else if (currentShape === 'ellipse') {
            ctx.beginPath();
            ctx.ellipse(x + width / 2, y + height / 2, width / 2, height / 2, 0, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
        } else { // rect
            ctx.fillRect(x, y, width, height);
            ctx.strokeRect(x, y, width, height);
        }

        // corner dots (bbox)
        ctx.fillStyle = '#06b6d4';
        ctx.fillRect(x - 3, y - 3, 6, 6);
        ctx.fillRect(x + width - 3, y - 3, 6, 6);
        ctx.fillRect(x - 3, y + height - 3, 6, 6);
        ctx.fillRect(x + width - 3, y + height - 3, 6, 6);
    }
}

// Update coordinate representation string
function updateCoordDisplay() {
    if (cropBox.width > 0) {
        const scaleX = originalWidth / (selectionCanvas.width || 1);
        const scaleY = originalHeight / (selectionCanvas.height || 1);

        const ox = Math.round(cropBox.x * scaleX);
        const oy = Math.round(cropBox.y * scaleY);
        const ow = Math.round(cropBox.width * scaleX);
        const oh = Math.round(cropBox.height * scaleY);

        const shapeNames = { rect: 'Vuông', diamond: 'Thoi', ellipse: 'Tròn', poly: 'Custom' };
        coordDisplay.innerText = `[${shapeNames[currentShape]}] ${ox}, ${oy} (${ow}x${oh}px)`;
    } else {
        coordDisplay.innerText = "Chưa chọn";
    }
}

// Shape selector buttons
function setupShapeListeners() {
    document.querySelectorAll('.shape-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.shape-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentShape = btn.dataset.shape;

            // Switching to/from lasso clears the current selection
            resetSelection();
            disableActions(null);

            if (canvasHint) {
                canvasHint.innerText = currentShape === 'poly'
                    ? 'Giữ chuột và vẽ tự do quanh logo, thả chuột để đóng vùng'
                    : 'Kéo thả chuột để vẽ vùng watermark theo hình đã chọn';
            }
        });
    });
}

// Setup listeners for VEO and VieON presets
function setupPresetListeners() {
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            if (!selectedVideo) return;
            const preset = btn.dataset.preset;

            document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Presets define a rectangle in original coords
            let ox, oy, ow, oh;
            if (preset === 'veo-text') {
                ox = 1215 * (originalWidth / 1280); oy = 680 * (originalHeight / 720);
                ow = 65 * (originalWidth / 1280);   oh = 40 * (originalHeight / 720);
            } else { // vieon-star
                ox = 1140 * (originalWidth / 1280); oy = 580 * (originalHeight / 720);
                ow = 70 * (originalWidth / 1280);   oh = 70 * (originalHeight / 720);
            }

            // place into canvas-buffer coords
            const scaleX = selectionCanvas.width / originalWidth;
            const scaleY = selectionCanvas.height / originalHeight;
            cropBox.x = ox * scaleX;
            cropBox.y = oy * scaleY;
            cropBox.width = ow * scaleX;
            cropBox.height = oh * scaleY;

            // presets are rectangular regions
            if (currentShape === 'poly') {
                document.querySelector('.shape-btn[data-shape="rect"]').click();
                // re-apply after reset
                cropBox.x = ox * scaleX; cropBox.y = oy * scaleY;
                cropBox.width = ow * scaleX; cropBox.height = oh * scaleY;
            }

            convertToOriginalCoords();
            drawSelection();
            updateCoordDisplay();
            enableActions();
        });
    });
}

// Call API to run auto variance-based watermark detection
async function runAutoDetection() {
    if (!selectedVideo) return;

    detectStatus.classList.remove('hidden');
    btnDetect.disabled = true;

    try {
        const res = await fetch('/api/detect_watermark', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video_name: selectedVideo })
        });
        const data = await res.json();

        detectStatus.classList.add('hidden');
        btnDetect.disabled = false;

        if (data.success && data.detected && data.detected.length > 0) {
            const wmark = data.detected[0];
            const bbox = wmark.bbox;

            const scaleX = selectionCanvas.width / originalWidth;
            const scaleY = selectionCanvas.height / originalHeight;

            const pad = 5;
            const px1 = Math.max(0, bbox.x - pad);
            const py1 = Math.max(0, bbox.y - pad);
            const px2 = Math.min(originalWidth, bbox.x + bbox.width + pad);
            const py2 = Math.min(originalHeight, bbox.y + bbox.height + pad);

            cropBox.x = px1 * scaleX;
            cropBox.y = py1 * scaleY;
            cropBox.width = (px2 - px1) * scaleX;
            cropBox.height = (py2 - py1) * scaleY;

            convertToOriginalCoords();
            drawSelection();
            updateCoordDisplay();
            enableActions();

            alert(`Đã tự động phát hiện watermark ở ${wmark.corner}!`);
        } else {
            alert("Không tìm thấy watermark tự động. Vui lòng tự vẽ vùng chọn bằng chuột.");
        }
    } catch (err) {
        detectStatus.classList.add('hidden');
        btnDetect.disabled = false;
        alert("Lỗi kết nối tới server khi quét watermark");
    }
}

// Build the shape payload sent to the backend
function buildShapePayload() {
    const method = document.querySelector('input[name="method"]:checked').value;
    const payload = {
        video_name: selectedVideo,
        x: cropBox.origX,
        y: cropBox.origY,
        width: cropBox.origWidth,
        height: cropBox.origHeight,
        shape: currentShape,
        method: method,
        params: collectParams()
    };
    if (currentShape === 'poly') payload.points = lassoOrigPoints;
    return payload;
}

// Render a before/after preview using the current method + slider params
async function runPreview(silent) {
    if (!selectedVideo || cropBox.width <= 0) return;

    baPreview.classList.remove('hidden');
    baLoading.classList.remove('hidden');
    if (!silent) {
        btnPreview.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Đang tạo preview...';
        btnPreview.disabled = true;
    }

    try {
        const res = await fetch('/api/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(buildShapePayload())
        });
        const data = await res.json();

        baLoading.classList.add('hidden');
        btnPreview.innerHTML = '<i class="fa-solid fa-images"></i> Tạo / Cập nhật Preview';
        btnPreview.disabled = false;

        if (data.success) {
            const bust = '?t=' + Date.now();
            baBefore.src = data.before_url + bust;
            baAfter.src = data.after_url + bust;
            if (data.stats) {
                baStats.innerText =
                    `Alpha TB: ${data.stats.alpha_mean} · Phủ: ${data.stats.static_percent}%`;
            } else {
                baStats.innerText = '';
            }
        } else if (!silent) {
            alert(`Lỗi tạo preview: ${data.error}`);
        }
    } catch (err) {
        baLoading.classList.add('hidden');
        btnPreview.innerHTML = '<i class="fa-solid fa-images"></i> Tạo / Cập nhật Preview';
        btnPreview.disabled = false;
        if (!silent) alert("Lỗi kết nối tới server khi tạo preview");
    }
}

// Call process API to process video
async function startProcessing() {
    if (!selectedVideo || cropBox.width <= 0) return;

    progressVideoName.innerText = `Video: ${selectedVideo}`;
    progressBarFill.style.width = '0%';
    progressText.innerText = '0';
    progressModalEl.classList.remove('hidden');

    try {
        const payload = buildShapePayload();
        const res = await fetch('/api/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (data.success) {
            pollStatus(data.task_id);
        } else {
            progressModalEl.classList.add('hidden');
            alert(`Lỗi bắt đầu xử lý: ${data.error}`);
        }
    } catch (err) {
        progressModalEl.classList.add('hidden');
        alert("Lỗi kết nối tới server khi gửi yêu cầu xử lý");
    }
}

// Poll processing progress from API
function pollStatus(taskId) {
    if (pollInterval) clearInterval(pollInterval);

    pollInterval = setInterval(async () => {
        try {
            const res = await fetch(`/api/status/${taskId}`);
            const data = await res.json();

            if (data.success) {
                const task = data.task;

                if (task.status === 'processing' || task.status === 'analyzing') {
                    progressBarFill.style.width = `${task.progress}%`;
                    progressText.innerText = task.progress;
                } else if (task.status === 'completed') {
                    clearInterval(pollInterval);
                    progressModalEl.classList.add('hidden');
                    resultFilepath.innerText = task.output_path;
                    resultModalEl.classList.remove('hidden');
                    loadVideos();
                } else if (task.status === 'failed') {
                    clearInterval(pollInterval);
                    progressModalEl.classList.add('hidden');
                    alert(`Quá trình xử lý thất bại: ${task.error}`);
                }
            } else {
                clearInterval(pollInterval);
                progressModalEl.classList.add('hidden');
                alert(`Lỗi check tiến độ: ${data.error}`);
            }
        } catch (err) {
            console.error("Polling error", err);
        }
    }, 500);
}
