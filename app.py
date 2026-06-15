import os
import subprocess
import cv2
import numpy as np
import threading
import uuid
from flask import Flask, jsonify, request, send_from_directory, render_template_string
from smart_remover import SmartWatermarkRemover
import config


def _get_ffmpeg_bin():
    """Resolve ffmpeg binary — prefer the one bundled with imageio/moviepy."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    try:
        from moviepy.config import FFMPEG_BINARY
        if FFMPEG_BINARY and os.path.isfile(FFMPEG_BINARY):
            return FFMPEG_BINARY
    except Exception:
        pass
    return "ffmpeg"

app = Flask(__name__)

VIDEOS_DIR = config.VIDEOS_DIR
os.makedirs(VIDEOS_DIR, exist_ok=True)
PREVIEW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "previews")
os.makedirs(PREVIEW_DIR, exist_ok=True)

# In-memory store for processing tasks
# task_id: { 'status': 'pending|processing|completed|failed', 'progress': 0, 'error': None, 'output_path': None }
tasks = {}

def build_roi_mask(w, h, shape, x1, y1, x2, y2, points=None):
    """Build a full-frame uint8 mask (255 inside the selected shape)."""
    mask = np.zeros((h, w), dtype=np.uint8)
    x1 = max(0, min(int(x1), w))
    y1 = max(0, min(int(y1), h))
    x2 = max(0, min(int(x2), w))
    y2 = max(0, min(int(y2), h))

    if shape == "poly" and points and len(points) >= 3:
        pts = np.array([[int(px), int(py)] for px, py in points], dtype=np.int32)
        cv2.fillPoly(mask, [pts], 255)
    elif shape == "diamond":
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        pts = np.array([[cx, y1], [x2, cy], [cx, y2], [x1, cy]], dtype=np.int32)
        cv2.fillPoly(mask, [pts], 255)
    elif shape == "ellipse":
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        ax, ay = max(1, (x2 - x1) // 2), max(1, (y2 - y1) // 2)
        cv2.ellipse(mask, (cx, cy), (ax, ay), 0, 0, 360, 255, -1)
    else:  # rect
        mask[y1:y2, x1:x2] = 255
    return mask


def get_video_size(video_path):
    cap = cv2.VideoCapture(video_path)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return w, h


def pick_busy_frame(video_path, x1, y1, x2, y2, samples=24):
    """Return (frame_index, BGR frame) where the ROI has the most texture/motion,
    so a before/after preview shows the watermark over a non-flat background."""
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    step = max(1, total // samples)
    best_var, best_idx, best_frame = -1.0, 0, None
    for i in range(0, total, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if not ret:
            continue
        roi = frame[y1:y2, x1:x2]
        v = float(roi.var()) if roi.size else 0.0
        if v > best_var:
            best_var, best_idx, best_frame = v, i, frame
    if best_frame is None:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        _, best_frame = cap.read()
    cap.release()
    return best_idx, best_frame


def apply_method_bgr(frame_bgr, method, mask, x1, y1, x2, y2, remover, params):
    """Apply removal to a BGR frame (no colour conversion needed — white is
    (255,255,255) in any channel order, and inpaint/blur are order-agnostic).
    Used by the video processing thread for zero-copy performance."""
    if method == "smart" and remover is not None:
        crop = frame_bgr[y1:y2, x1:x2]
        processed = remover.process_frame(crop)
        out = frame_bgr.copy()
        out[y1:y2, x1:x2] = processed
        return out
    if method == "inpaint":
        radius = int(params.get("radius", 5)) if params else 5
        radius = max(1, min(radius, 25))
        return cv2.inpaint(frame_bgr, mask, radius, cv2.INPAINT_TELEA)
    # blur
    ksize = int(params.get("blur", 25)) if params else 25
    ksize = max(3, ksize | 1)
    blurred = cv2.GaussianBlur(frame_bgr, (ksize, ksize), 0)
    out = frame_bgr.copy()
    out[mask > 0] = blurred[mask > 0]
    return out


def apply_method_rgb(frame_rgb, method, mask, x1, y1, x2, y2, remover, params):
    """RGB wrapper used by the preview endpoint (keeps existing interface)."""
    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    out_bgr = apply_method_bgr(frame_bgr, method, mask, x1, y1, x2, y2, remover, params)
    return cv2.cvtColor(out_bgr, cv2.COLOR_BGR2RGB)


def get_mp4_files():
    files = []
    for f in os.listdir(VIDEOS_DIR):
        if f.lower().endswith(".mp4") and not f.endswith("_no_watermark.mp4"):
            path = os.path.join(VIDEOS_DIR, f)
            try:
                stat = os.stat(path)
                files.append({
                    "name": f,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime
                })
            except Exception:
                pass
    # Sort by modification time (newest first)
    files.sort(key=lambda x: x["mtime"], reverse=True)
    return files

@app.route("/")
def index():
    # We will serve the index.html via send_from_directory or render it
    return send_from_directory("templates", "index.html")

@app.route("/static/<path:path>")
def serve_static(path):
    return send_from_directory("static", path)

@app.route("/previews/<path:path>")
def serve_preview(path):
    return send_from_directory(PREVIEW_DIR, path)

@app.route("/api/videos", methods=["GET"])
def api_videos():
    try:
        videos = get_mp4_files()
        return jsonify({"success": True, "videos": videos})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/extract_frame", methods=["POST"])
def api_extract_frame():
    data = request.json or {}
    video_name = data.get("video_name")
    if not video_name:
        return jsonify({"success": False, "error": "Missing video_name"})
    
    video_path = os.path.join(VIDEOS_DIR, video_name)
    if not os.path.exists(video_path):
        return jsonify({"success": False, "error": "Video not found"})
    
    preview_name = f"{video_name}_preview.png"
    preview_path = os.path.join(PREVIEW_DIR, preview_name)
    
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return jsonify({"success": False, "error": "Cannot open video"})
        
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps if fps > 0 else 0
        
        # Seek to 1 second (or 10% of video if shorter than 1s)
        seek_msec = 1000 if duration > 1.0 else int(duration * 100)
        cap.set(cv2.CAP_PROP_POS_MSEC, seek_msec)
        
        ret, frame = cap.read()
        if not ret:
            # Fallback to first frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
            
        if ret:
            cv2.imwrite(preview_path, frame)
            cap.release()
            return jsonify({
                "success": True,
                "preview_url": f"/previews/{preview_name}",
                "width": w,
                "height": h,
                "duration": duration
            })
        else:
            cap.release()
            return jsonify({"success": False, "error": "Could not read frame"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/detect_watermark", methods=["POST"])
def api_detect_watermark():
    data = request.json or {}
    video_name = data.get("video_name")
    if not video_name:
        return jsonify({"success": False, "error": "Missing video_name"})
    
    video_path = os.path.join(VIDEOS_DIR, video_name)
    if not os.path.exists(video_path):
        return jsonify({"success": False, "error": "Video not found"})
    
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return jsonify({"success": False, "error": "Cannot open video"})
        
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Read ~20 frames distributed evenly
        frames = []
        step = max(1, total_frames // 20)
        for i in range(0, total_frames, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if ret:
                frames.append(frame)
            if len(frames) >= 20:
                break
        cap.release()
        
        if not frames:
            return jsonify({"success": False, "error": "No frames read"})
            
        frames = np.array(frames)
        # Calculate pixel-wise variance across frames
        var_img = np.var(frames, axis=0)
        mean_img = np.mean(frames, axis=0).astype(np.uint8)
        
        # Convert variance to grayscale (average over color channels)
        var_gray = np.mean(var_img, axis=2)
        mean_gray = cv2.cvtColor(mean_img, cv2.COLOR_BGR2GRAY)
        
        # Threshold: low variance (static pixels) and not pitch black
        static_mask = (var_gray < 8.0) & (mean_gray > 30)
        static_mask_img = np.zeros_like(var_gray, dtype=np.uint8)
        static_mask_img[static_mask] = 255
        
        # We only search the 4 corners: 25% margin from edges
        x_margin = int(w * 0.25)
        y_margin = int(h * 0.25)
        
        corners = {
            "top_left": (0, 0, x_margin, y_margin),
            "top_right": (w - x_margin, 0, w, y_margin),
            "bottom_left": (0, h - y_margin, x_margin, h),
            "bottom_right": (w - x_margin, h - y_margin, w, h)
        }
        
        detected_watermarks = []
        
        for corner_name, (x1, y1, x2, y2) in corners.items():
            corner_mask = static_mask_img[y1:y2, x1:x2]
            # Find connected components in this corner
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(corner_mask)
            
            for i in range(1, num_labels):
                area = stats[i, cv2.CC_STAT_AREA]
                comp_w = stats[i, cv2.CC_STAT_WIDTH]
                comp_h = stats[i, cv2.CC_STAT_HEIGHT]
                comp_x = stats[i, cv2.CC_STAT_LEFT] + x1
                comp_y = stats[i, cv2.CC_STAT_TOP] + y1
                
                # Filter by component dimensions: watermark should be tiny but reasonable
                # between 10x10 and 150x150 pixels for a 720p video
                scale = h / 720.0
                min_dim = int(10 * scale)
                max_dim = int(150 * scale)
                min_area = int(50 * scale * scale)
                max_area = int(12000 * scale * scale)
                
                if min_dim <= comp_w <= max_dim and min_dim <= comp_h <= max_dim and min_area <= area <= max_area:
                    # Check that it's not touching the absolute screen borders (could be black bars)
                    if comp_x > 2 and comp_y > 2 and (comp_x + comp_w) < w - 2 and (comp_y + comp_h) < h - 2:
                        detected_watermarks.append({
                            "corner": corner_name,
                            "bbox": {
                                "x": int(comp_x),
                                "y": int(comp_y),
                                "width": int(comp_w),
                                "height": int(comp_h)
                            },
                            "area": int(area)
                        })
        
        # Sort detected watermarks by area to return the most prominent ones
        detected_watermarks.sort(key=lambda x: x["area"], reverse=True)
        
        return jsonify({
            "success": True, 
            "detected": detected_watermarks
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

def process_video_thread(task_id, video_path, output_path, x1, y1, x2, y2,
                         method, sensitivity='medium', roi_mask=None, params=None):
    """Process a video using direct OpenCV I/O + ffmpeg pipe for maximum speed.

    Replaces the MoviePy approach which paid Python overhead on every frame.
    Frames are read with VideoCapture, processed in-place on the ROI only, then
    streamed as raw BGR bytes into an ffmpeg process that encodes libx264 and
    muxes the original audio — all in a single pass, no temp files.
    """
    try:
        params = params or {}

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise Exception("Cannot open video")

        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1

        # Prepare shape mask
        if roi_mask is not None:
            mask = roi_mask if roi_mask.shape[:2] == (h, w) else \
                   cv2.resize(roi_mask, (w, h), interpolation=cv2.INTER_NEAREST)
        else:
            mask = np.zeros((h, w), dtype=np.uint8)
            mask[y1:y2, x1:x2] = 255

        # --- Analyze (smart only) ---
        remover = None
        if method == "smart":
            tasks[task_id]["status"] = "analyzing"
            remover = SmartWatermarkRemover(sensitivity=sensitivity)
            remover.analyze(video_path, (x1, y1, x2, y2), roi_mask=mask,
                            gain=params.get("gain"), floor=params.get("floor"),
                            edge_expand=params.get("edge"),
                            tophat_thr=params.get("tophat"),
                            despill=params.get("despill"),
                            edge_blur=params.get("edge_blur"))

        tasks[task_id]["status"] = "processing"

        # --- Encode via ffmpeg pipe (no temp file, audio muxed in one pass) ---
        ffmpeg = _get_ffmpeg_bin()
        cmd = [
            ffmpeg, '-y',
            # video input: raw BGR frames from stdin
            '-f', 'rawvideo', '-vcodec', 'rawvideo',
            '-s', f'{w}x{h}', '-pix_fmt', 'bgr24', '-r', str(fps),
            '-i', 'pipe:0',
            # audio input: original file
            '-i', video_path,
            # outputs
            '-vcodec', 'libx264', '-preset', 'fast', '-crf', '18',
            '-c:a', 'aac', '-b:a', '128k',
            '-map', '0:v:0', '-map', '1:a:0?',  # ? = audio optional
            '-shortest',
            output_path,
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)

        frame_idx = 0
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                out = apply_method_bgr(frame, method, mask,
                                       x1, y1, x2, y2, remover, params)
                proc.stdin.write(out.tobytes())
                frame_idx += 1
                tasks[task_id]["progress"] = min(
                    int(frame_idx / total_frames * 100), 99)
        finally:
            cap.release()
            proc.stdin.close()

        proc.wait()
        if proc.returncode != 0:
            raise Exception(f"FFmpeg encoding failed (exit {proc.returncode})")

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["output_path"] = output_path

    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)

@app.route("/api/preview", methods=["POST"])
def api_preview():
    """Render a before/after preview of the chosen method+params on a single
    representative (busy-background) frame, so the user can tune and see the
    exact result before processing the whole video."""
    data = request.json or {}
    video_name = data.get("video_name")
    x = data.get("x")
    y = data.get("y")
    width = data.get("width")
    height = data.get("height")
    method = data.get("method", "smart")
    sensitivity = data.get("sensitivity", "medium")
    shape = data.get("shape", "rect")
    points = data.get("points")
    params = data.get("params") or {}

    if not video_name or x is None or y is None or width is None or height is None:
        return jsonify({"success": False, "error": "Missing parameters"})

    video_path = os.path.join(VIDEOS_DIR, video_name)
    if not os.path.exists(video_path):
        return jsonify({"success": False, "error": "Video not found"})

    x1 = max(0, int(x))
    y1 = max(0, int(y))
    x2 = int(x + width)
    y2 = int(y + height)
    if x2 <= x1 or y2 <= y1:
        return jsonify({"success": False, "error": "Invalid region"})

    try:
        fw, fh = get_video_size(video_path)
        roi_mask = build_roi_mask(fw, fh, shape, x1, y1, x2, y2, points)

        remover = None
        stats = None
        if method == "smart":
            remover = SmartWatermarkRemover(sensitivity=sensitivity)
            stats = remover.analyze(video_path, (x1, y1, x2, y2), roi_mask=roi_mask,
                                    gain=params.get("gain"), floor=params.get("floor"),
                                    edge_expand=params.get("edge"),
                                    tophat_thr=params.get("tophat"),
                                    despill=params.get("despill"),
                                    edge_blur=params.get("edge_blur"))

        _, frame_bgr = pick_busy_frame(video_path, x1, y1, x2, y2)
        after_bgr = apply_method_bgr(frame_bgr, method, roi_mask,
                                     x1, y1, x2, y2, remover, params)

        # Crop a padded region around the selection for a focused before/after.
        pad = int(0.5 * max(x2 - x1, y2 - y1)) + 10
        cx1 = max(0, x1 - pad); cy1 = max(0, y1 - pad)
        cx2 = min(fw, x2 + pad); cy2 = min(fh, y2 + pad)
        before_crop = frame_bgr[cy1:cy2, cx1:cx2]
        after_crop = after_bgr[cy1:cy2, cx1:cx2]

        stamp = uuid.uuid4().hex[:8]
        before_name = f"{video_name}_prev_before_{stamp}.png"
        after_name = f"{video_name}_prev_after_{stamp}.png"
        cv2.imwrite(os.path.join(PREVIEW_DIR, before_name), before_crop)
        cv2.imwrite(os.path.join(PREVIEW_DIR, after_name), after_crop)

        return jsonify({
            "success": True,
            "before_url": f"/previews/{before_name}",
            "after_url": f"/previews/{after_name}",
            "stats": stats,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/process", methods=["POST"])
def api_process():
    data = request.json or {}
    video_name = data.get("video_name")
    x = data.get("x")
    y = data.get("y")
    width = data.get("width")
    height = data.get("height")
    method = data.get("method", "smart") # smart, inpaint or blur
    sensitivity = data.get("sensitivity", "medium")
    shape = data.get("shape", "rect")
    points = data.get("points")
    params = data.get("params") or {}

    if not video_name or x is None or y is None or width is None or height is None:
        return jsonify({"success": False, "error": "Missing parameters"})

    video_path = os.path.join(VIDEOS_DIR, video_name)
    if not os.path.exists(video_path):
        return jsonify({"success": False, "error": "Video not found"})

    # Generate output path
    base, ext = os.path.splitext(video_name)
    output_name = f"{base}_no_watermark{ext}"
    output_path = os.path.join(VIDEOS_DIR, output_name)

    # Check boundaries
    x1 = max(0, int(x))
    y1 = max(0, int(y))
    x2 = int(x + width)
    y2 = int(y + height)

    # Build shape-aware ROI mask once
    cap = cv2.VideoCapture(video_path)
    fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    roi_mask = build_roi_mask(fw, fh, shape, x1, y1, x2, y2, points)

    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "error": None,
        "output_path": None,
        "video_name": video_name,
        "output_name": output_name
    }
    
    thread = threading.Thread(
        target=process_video_thread,
        args=(task_id, video_path, output_path, x1, y1, x2, y2, method, sensitivity, roi_mask, params)
    )
    thread.start()
    
    return jsonify({"success": True, "task_id": task_id})

@app.route("/api/status/<task_id>", methods=["GET"])
def api_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({"success": False, "error": "Task not found"})
    return jsonify({"success": True, "task": task})

if __name__ == "__main__":
    print(f"Videos directory : {VIDEOS_DIR}")
    print(f"Starting server on http://{config.HOST}:{config.PORT}")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
