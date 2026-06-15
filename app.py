import os
import json
import subprocess
import threading
import uuid

import cv2
import numpy as np
from flask import Flask, jsonify, request, send_from_directory

from smart_remover import SmartWatermarkRemover
import config


app = Flask(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PREVIEW_DIR = os.path.join(BASE_DIR, "previews")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
os.makedirs(PREVIEW_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Settings persistence (folder remembered across restarts)
# ---------------------------------------------------------------------------
def _load_settings() -> dict:
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_settings(updates: dict) -> None:
    data = _load_settings()
    data.update(updates)
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


_settings = _load_settings()
_videos_dir: list = [_settings.get("videos_dir", config.VIDEOS_DIR)]

# ---------------------------------------------------------------------------
# File-type helpers
# ---------------------------------------------------------------------------
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".m4v", ".webm"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}


def _ext(name: str) -> str:
    return os.path.splitext(name)[1].lower()


def is_video(name: str) -> bool:
    return _ext(name) in VIDEO_EXTS


def is_image(name: str) -> bool:
    return _ext(name) in IMAGE_EXTS


# ---------------------------------------------------------------------------
# ffmpeg binary
# ---------------------------------------------------------------------------
def _get_ffmpeg_bin() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    return "ffmpeg"


# ---------------------------------------------------------------------------
# ROI mask builder
# ---------------------------------------------------------------------------
def build_roi_mask(w, h, shape, x1, y1, x2, y2, points=None):
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
    else:
        mask[y1:y2, x1:x2] = 255
    return mask


# ---------------------------------------------------------------------------
# Video helpers
# ---------------------------------------------------------------------------
def get_video_size(video_path):
    cap = cv2.VideoCapture(video_path)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return w, h


def pick_busy_frame(video_path, x1, y1, x2, y2, samples=24):
    """Return (frame_index, BGR frame) with max ROI texture for a preview."""
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    step = max(1, total // samples)
    best_var, best_frame = -1.0, None
    frame_idx = 0
    while True:
        if frame_idx % step == 0:
            ret, frame = cap.read()
            if not ret:
                break
            roi = frame[y1:y2, x1:x2]
            v = float(roi.var()) if roi.size else 0.0
            if v > best_var:
                best_var, best_frame = v, frame
        else:
            if not cap.grab():
                break
        frame_idx += 1
    if best_frame is None:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        _, best_frame = cap.read()
    cap.release()
    return best_frame


# ---------------------------------------------------------------------------
# Processing helpers (shared by preview + video thread + image endpoint)
# ---------------------------------------------------------------------------
def apply_method_bgr(frame_bgr, method, mask, x1, y1, x2, y2, remover, params):
    """Apply removal on a BGR frame. White = 255 in any channel order."""
    if method == "smart" and remover is not None:
        crop = frame_bgr[y1:y2, x1:x2]
        out = frame_bgr.copy()
        out[y1:y2, x1:x2] = remover.process_frame(crop)
        return out
    if method == "inpaint":
        radius = max(1, min(int((params or {}).get("radius", 5)), 25))
        return cv2.inpaint(frame_bgr, mask, radius, cv2.INPAINT_TELEA)
    ksize = max(3, int((params or {}).get("blur", 25)) | 1)
    blurred = cv2.GaussianBlur(frame_bgr, (ksize, ksize), 0)
    out = frame_bgr.copy()
    out[mask > 0] = blurred[mask > 0]
    return out


def apply_method_rgb(frame_rgb, method, mask, x1, y1, x2, y2, remover, params):
    """RGB wrapper (used by preview endpoint)."""
    bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    return cv2.cvtColor(
        apply_method_bgr(bgr, method, mask, x1, y1, x2, y2, remover, params),
        cv2.COLOR_BGR2RGB,
    )


# ---------------------------------------------------------------------------
# File listing
# ---------------------------------------------------------------------------
def get_files():
    folder = _videos_dir[0]
    if not os.path.isdir(folder):
        return []
    files = []
    try:
        entries = os.listdir(folder)
    except PermissionError:
        return []
    for f in entries:
        if f.endswith("_no_watermark" + _ext(f)):
            continue
        if not (is_video(f) or is_image(f)):
            continue
        path = os.path.join(folder, f)
        try:
            stat = os.stat(path)
            files.append({
                "name": f,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "type": "image" if is_image(f) else "video",
            })
        except Exception:
            pass
    files.sort(key=lambda x: x["mtime"], reverse=True)
    return files


# ---------------------------------------------------------------------------
# In-memory task store
# ---------------------------------------------------------------------------
tasks = {}

# ---------------------------------------------------------------------------
# Routes — static / index
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory("templates", "index.html")


@app.route("/static/<path:path>")
def serve_static(path):
    return send_from_directory("static", path)


@app.route("/previews/<path:path>")
def serve_preview(path):
    return send_from_directory(PREVIEW_DIR, path)


# ---------------------------------------------------------------------------
# Folder API
# ---------------------------------------------------------------------------
@app.route("/api/current_folder", methods=["GET"])
def api_current_folder():
    return jsonify({"success": True, "folder": _videos_dir[0]})


@app.route("/api/browse_folder", methods=["POST"])
def api_browse_folder():
    """Open a native OS folder-picker dialog via tkinter and return the chosen path."""
    result = {"folder": None, "error": None}
    done = threading.Event()

    def _open():
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            folder = filedialog.askdirectory(title="Chọn thư mục chứa video / ảnh")
            root.destroy()
            result["folder"] = folder or None
        except Exception as e:
            result["error"] = str(e)
        finally:
            done.set()

    t = threading.Thread(target=_open, daemon=True)
    t.start()
    done.wait(timeout=120)

    if result["error"]:
        return jsonify({"success": False, "error": result["error"]})
    if result["folder"]:
        return jsonify({"success": True, "folder": os.path.normpath(result["folder"])})
    return jsonify({"success": False, "cancelled": True})


@app.route("/api/set_folder", methods=["POST"])
def api_set_folder():
    data = request.json or {}
    folder = data.get("folder", "").strip()
    if not folder:
        return jsonify({"success": False, "error": "Đường dẫn trống"})
    if not os.path.isdir(folder):
        return jsonify({"success": False, "error": "Thư mục không tồn tại"})
    _videos_dir[0] = folder
    _save_settings({"videos_dir": folder})
    return jsonify({"success": True, "folder": folder})


# ---------------------------------------------------------------------------
# File / video list
# ---------------------------------------------------------------------------
@app.route("/api/videos", methods=["GET"])
def api_videos():
    try:
        return jsonify({"success": True, "videos": get_files(),
                        "folder": _videos_dir[0]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ---------------------------------------------------------------------------
# Extract preview frame
# ---------------------------------------------------------------------------
@app.route("/api/extract_frame", methods=["POST"])
def api_extract_frame():
    data = request.json or {}
    name = data.get("video_name")
    if not name:
        return jsonify({"success": False, "error": "Missing video_name"})

    path = os.path.join(_videos_dir[0], name)
    if not os.path.exists(path):
        return jsonify({"success": False, "error": "File not found"})

    preview_name = f"{name}_preview.png"
    preview_path = os.path.join(PREVIEW_DIR, preview_name)

    try:
        if is_image(name):
            img = cv2.imread(path)
            if img is None:
                return jsonify({"success": False, "error": "Cannot read image"})
            h, w = img.shape[:2]
            cv2.imwrite(preview_path, img)
            return jsonify({
                "success": True,
                "preview_url": f"/previews/{preview_name}",
                "width": w, "height": h, "duration": 0, "type": "image"
            })

        # --- video ---
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return jsonify({"success": False, "error": "Cannot open video"})
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
        cap.set(cv2.CAP_PROP_POS_MSEC, 1000 if duration > 1.0 else int(duration * 100))
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
        cap.release()
        if not ret:
            return jsonify({"success": False, "error": "Could not read frame"})
        cv2.imwrite(preview_path, frame)
        return jsonify({
            "success": True,
            "preview_url": f"/previews/{preview_name}",
            "width": w, "height": h, "duration": duration, "type": "video"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ---------------------------------------------------------------------------
# Auto-detect watermark (video-only)
# ---------------------------------------------------------------------------
@app.route("/api/detect_watermark", methods=["POST"])
def api_detect_watermark():
    data = request.json or {}
    name = data.get("video_name")
    if not name:
        return jsonify({"success": False, "error": "Missing video_name"})
    if is_image(name):
        return jsonify({"success": True, "detected": []})

    path = os.path.join(_videos_dir[0], name)
    if not os.path.exists(path):
        return jsonify({"success": False, "error": "File not found"})

    try:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return jsonify({"success": False, "error": "Cannot open video"})
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        step = max(1, total // 20)
        frames = []
        idx = 0
        while len(frames) < 20:
            if idx % step == 0:
                ret, frame = cap.read()
                if not ret:
                    break
                frames.append(frame)
            else:
                if not cap.grab():
                    break
            idx += 1
        cap.release()
        if not frames:
            return jsonify({"success": False, "error": "No frames read"})

        arr = np.array(frames)
        var_gray = np.mean(np.var(arr, axis=0), axis=2)
        mean_gray = cv2.cvtColor(np.mean(arr, axis=0).astype(np.uint8),
                                 cv2.COLOR_BGR2GRAY)
        static_mask = ((var_gray < 8.0) & (mean_gray > 30)).astype(np.uint8) * 255

        x_m, y_m = int(w * 0.25), int(h * 0.25)
        corners = {
            "top_left":     (0,     0,     x_m,   y_m),
            "top_right":    (w-x_m, 0,     w,     y_m),
            "bottom_left":  (0,     h-y_m, x_m,   h),
            "bottom_right": (w-x_m, h-y_m, w,     h),
        }
        detected = []
        scale = h / 720.0
        for corner, (cx1, cy1, cx2, cy2) in corners.items():
            region = static_mask[cy1:cy2, cx1:cx2]
            num, _, stats, _ = cv2.connectedComponentsWithStats(region)
            for i in range(1, num):
                cw = stats[i, cv2.CC_STAT_WIDTH]
                ch_ = stats[i, cv2.CC_STAT_HEIGHT]
                area = stats[i, cv2.CC_STAT_AREA]
                bx = stats[i, cv2.CC_STAT_LEFT] + cx1
                by = stats[i, cv2.CC_STAT_TOP] + cy1
                mn, mx = int(10*scale), int(150*scale)
                if (mn <= cw <= mx and mn <= ch_ <= mx
                        and int(50*scale*scale) <= area <= int(12000*scale*scale)
                        and bx > 2 and by > 2
                        and bx+cw < w-2 and by+ch_ < h-2):
                    detected.append({"corner": corner,
                                     "bbox": {"x": int(bx), "y": int(by),
                                              "width": int(cw), "height": int(ch_)},
                                     "area": int(area)})
        detected.sort(key=lambda x: x["area"], reverse=True)
        return jsonify({"success": True, "detected": detected})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ---------------------------------------------------------------------------
# Preview (before/after, single frame)
# ---------------------------------------------------------------------------
def _parse_region(data):
    x = data.get("x"); y = data.get("y")
    w = data.get("width"); h = data.get("height")
    if None in (x, y, w, h):
        return None, "Missing region parameters"
    x1 = max(0, int(x)); y1 = max(0, int(y))
    x2 = int(x + w);     y2 = int(y + h)
    if x2 <= x1 or y2 <= y1:
        return None, "Invalid region"
    return (x1, y1, x2, y2), None


@app.route("/api/preview", methods=["POST"])
def api_preview():
    data = request.json or {}
    name = data.get("video_name")
    method = data.get("method", "smart")
    sensitivity = data.get("sensitivity", "medium")
    shape = data.get("shape", "rect")
    points = data.get("points")
    params = data.get("params") or {}

    if not name:
        return jsonify({"success": False, "error": "Missing video_name"})

    region, err = _parse_region(data)
    if err:
        return jsonify({"success": False, "error": err})
    x1, y1, x2, y2 = region

    path = os.path.join(_videos_dir[0], name)
    if not os.path.exists(path):
        return jsonify({"success": False, "error": "File not found"})

    try:
        file_is_image = is_image(name)

        if file_is_image:
            fw, fh = cv2.imread(path).shape[1], cv2.imread(path).shape[0]
        else:
            fw, fh = get_video_size(path)

        roi_mask = build_roi_mask(fw, fh, shape, x1, y1, x2, y2, points)

        remover = None
        stats = None
        if method == "smart":
            remover = SmartWatermarkRemover(sensitivity=sensitivity)
            if file_is_image:
                img_bgr = cv2.imread(path)
                stats = remover.analyze_image(
                    img_bgr, (x1, y1, x2, y2), roi_mask=roi_mask,
                    gain=params.get("gain"), floor=params.get("floor"),
                    edge_expand=params.get("edge"), tophat_thr=params.get("tophat"),
                    despill=params.get("despill"), edge_blur=params.get("edge_blur"))
                frame_bgr = img_bgr
            else:
                stats = remover.analyze(
                    path, (x1, y1, x2, y2), roi_mask=roi_mask,
                    gain=params.get("gain"), floor=params.get("floor"),
                    edge_expand=params.get("edge"), tophat_thr=params.get("tophat"),
                    despill=params.get("despill"), edge_blur=params.get("edge_blur"))
                frame_bgr = pick_busy_frame(path, x1, y1, x2, y2)
        else:
            frame_bgr = (cv2.imread(path) if file_is_image
                         else pick_busy_frame(path, x1, y1, x2, y2))

        after_bgr = apply_method_bgr(frame_bgr, method, roi_mask,
                                     x1, y1, x2, y2, remover, params)

        pad = int(0.5 * max(x2-x1, y2-y1)) + 10
        cx1 = max(0, x1-pad); cy1 = max(0, y1-pad)
        cx2 = min(fw, x2+pad); cy2 = min(fh, y2+pad)

        stamp = uuid.uuid4().hex[:8]
        before_name = f"prev_before_{stamp}.png"
        after_name  = f"prev_after_{stamp}.png"
        cv2.imwrite(os.path.join(PREVIEW_DIR, before_name), frame_bgr[cy1:cy2, cx1:cx2])
        cv2.imwrite(os.path.join(PREVIEW_DIR, after_name),  after_bgr[cy1:cy2,  cx1:cx2])

        return jsonify({
            "success": True,
            "before_url": f"/previews/{before_name}",
            "after_url":  f"/previews/{after_name}",
            "stats": stats,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ---------------------------------------------------------------------------
# Process single IMAGE (sync)
# ---------------------------------------------------------------------------
@app.route("/api/process_image", methods=["POST"])
def api_process_image():
    data = request.json or {}
    name = data.get("video_name")
    method = data.get("method", "smart")
    sensitivity = data.get("sensitivity", "medium")
    shape = data.get("shape", "rect")
    points = data.get("points")
    params = data.get("params") or {}

    region, err = _parse_region(data)
    if err:
        return jsonify({"success": False, "error": err})
    x1, y1, x2, y2 = region

    path = os.path.join(_videos_dir[0], name)
    if not os.path.exists(path):
        return jsonify({"success": False, "error": "File not found"})

    try:
        img = cv2.imread(path)
        if img is None:
            return jsonify({"success": False, "error": "Cannot read image"})
        fh, fw = img.shape[:2]
        roi_mask = build_roi_mask(fw, fh, shape, x1, y1, x2, y2, points)

        remover = None
        if method == "smart":
            remover = SmartWatermarkRemover(sensitivity=sensitivity)
            remover.analyze_image(
                img, (x1, y1, x2, y2), roi_mask=roi_mask,
                gain=params.get("gain"), floor=params.get("floor"),
                edge_expand=params.get("edge"), tophat_thr=params.get("tophat"),
                despill=params.get("despill"), edge_blur=params.get("edge_blur"))

        out = apply_method_bgr(img, method, roi_mask, x1, y1, x2, y2, remover, params)

        base, ext = os.path.splitext(name)
        output_name = f"{base}_no_watermark{ext}"
        output_path = os.path.join(_videos_dir[0], output_name)
        cv2.imwrite(output_path, out)

        return jsonify({"success": True,
                        "output_path": output_path,
                        "output_name": output_name})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ---------------------------------------------------------------------------
# Process VIDEO (async thread + polling)
# ---------------------------------------------------------------------------
def process_video_thread(task_id, video_path, output_path,
                         x1, y1, x2, y2, method, sensitivity,
                         roi_mask, params):
    try:
        params = params or {}

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise Exception("Cannot open video")
        w   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1

        mask = (roi_mask if roi_mask is not None and roi_mask.shape[:2] == (h, w)
                else cv2.resize(roi_mask, (w, h), interpolation=cv2.INTER_NEAREST)
                if roi_mask is not None
                else (lambda m: (m.__setitem__((slice(y1, y2), slice(x1, x2)), 255), m)[1])(
                    np.zeros((h, w), dtype=np.uint8)))

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

        ffmpeg = _get_ffmpeg_bin()
        cmd = [
            ffmpeg, "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{w}x{h}", "-pix_fmt", "bgr24", "-r", str(fps),
            "-i", "pipe:0",
            "-i", video_path,
            "-vcodec", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "128k",
            "-map", "0:v:0", "-map", "1:a:0?",
            "-shortest", output_path,
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        idx = 0
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                out = apply_method_bgr(frame, method, mask,
                                       x1, y1, x2, y2, remover, params)
                proc.stdin.write(out.tobytes())
                idx += 1
                tasks[task_id]["progress"] = min(int(idx / total * 100), 99)
        finally:
            cap.release()
            proc.stdin.close()

        proc.wait()
        if proc.returncode != 0:
            raise Exception(f"FFmpeg failed (exit {proc.returncode})")

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["output_path"] = output_path

    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)


@app.route("/api/process", methods=["POST"])
def api_process():
    data = request.json or {}
    name = data.get("video_name")
    method = data.get("method", "smart")
    sensitivity = data.get("sensitivity", "medium")
    shape = data.get("shape", "rect")
    points = data.get("points")
    params = data.get("params") or {}

    region, err = _parse_region(data)
    if err:
        return jsonify({"success": False, "error": err})
    x1, y1, x2, y2 = region

    path = os.path.join(_videos_dir[0], name)
    if not os.path.exists(path):
        return jsonify({"success": False, "error": "File not found"})

    base, ext = os.path.splitext(name)
    output_name = f"{base}_no_watermark{ext}"
    output_path = os.path.join(_videos_dir[0], output_name)

    cap = cv2.VideoCapture(path)
    fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    roi_mask = build_roi_mask(fw, fh, shape, x1, y1, x2, y2, points)

    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "status": "pending", "progress": 0, "error": None,
        "output_path": None, "video_name": name, "output_name": output_name,
    }
    threading.Thread(
        target=process_video_thread,
        args=(task_id, path, output_path, x1, y1, x2, y2,
              method, sensitivity, roi_mask, params),
        daemon=True,
    ).start()
    return jsonify({"success": True, "task_id": task_id})


@app.route("/api/status/<task_id>", methods=["GET"])
def api_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({"success": False, "error": "Task not found"})
    return jsonify({"success": True, "task": task})


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Videos / images folder : {_videos_dir[0]}")
    print(f"Starting server        : http://{config.HOST}:{config.PORT}")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG,
            use_reloader=False)
