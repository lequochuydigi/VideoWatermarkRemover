# 📝 Changelog

## [2.0.0] — 2026-06-18

### 🎯 Major: Stability & Performance

#### ✅ Fixes
- **Timeout protection**: Wrap `compute_median()` with 30s timeout — prevents hanging on unsupported codecs (H.265, AV1, VP9)
- **Smart retry**: If analyze times out, auto-retry with 8 frames instead of 20 (quick mode)
- **Frame extraction**: Replace `cv2.VideoCapture` with ffmpeg subprocess (20s timeout) for frame extraction — never hangs again
- **Error messages**: Show clear toast notifications instead of silent failures
- **Video codec support**: Handle corrupted/unusual video formats gracefully with fallback

#### 🚀 Performance
- **Speed optimization** (v1.2): Temporal median caching — first preview ~2-5s, subsequent changes <0.5s
- **Reduced samples**: `pick_busy_frame` uses 8 samples instead of 24 for faster initial loading
- Cache frame preview between preview updates (prevent re-reading video)

#### 🎨 UI/UX
- **Layout restructure**: Horizontal 3-step bar at top (file select → settings → process) — canvas gets full height
- **Sensitivity selector**: Add low/medium/high AI sensitivity toggle in Step 3
- **Toast notifications**: Beautiful floating error/success messages (no more alerts)
- **Better error feedback**: Timeouts show "Quick mode activated" instead of failing silently

#### 📚 Documentation
- Add `TROUBLESHOOTING.md` — codec issues, timeouts, performance tips
- Add `CHANGELOG.md` (this file)
- Update `.gitignore` — protect `settings.json`, ignore all video types
- Update `README.md` — explain async frame extraction, timeout behavior

#### 🔒 Security
- `settings.json` now properly ignored in `.gitignore`
- Local-only warning: No data sent to cloud, all processing on your machine
- Settings contain only folder path, safe to commit (but properly ignored anyway)

---

## [1.3.0] — 2026-06-17

### ✅ Fixes
- Frame extraction now uses ffmpeg subprocess (20s timeout) instead of hanging cv2.VideoCapture
- Add `_extract_frame_ffmpeg()` helper — handles all codecs, never blocks
- Thread-based `pick_busy_frame()` with 15s timeout + ffmpeg fallback
- Better metadata retrieval via `_get_video_meta()` with threading

---

## [1.2.0] — 2026-06-16

### 🚀 Performance
- **Caching**: Temporal median cache per bbox prevents re-reading video on slider changes
- **Frame cache**: Preview frame stored in memory for instant reuse
- Split `analyze()` into `compute_median()` (slow I/O) + `fit_from_median()` (fast compute)
- Reduce `pick_busy_frame` samples from 24 → 8

---

## [1.1.0] — 2026-06-15

### 🎨 UI/UX
- **Horizontal 3-step layout**: Top bar with file select, settings, process controls
- **Sensitivity selector**: Low / Medium / High buttons for AI tuning
- **Improved canvas**: Canvas now takes up full available height (no left sidebar eating space)
- **Compact Step 2**: Method selector now horizontal (3 columns) instead of vertical cards

---

## [1.0.0] — 2026-06-10

### 🎉 Release: Antigravity Watermark Eraser

#### Core Features
- ✅ Remove watermarks from videos & images
- ✅ 3 methods: Smart AI (reverse alpha blending), Inpaint, Blur
- ✅ Web UI on `localhost:8080` — no external connection
- ✅ Shape selector: Rectangle, Diamond, Circle, Lasso (free-form)
- ✅ Preset watermarks: VEO logo, VieON star
- ✅ Auto-detect watermark position
- ✅ Live preview (Before/After) with slider adjustments
- ✅ Batch file + Python venv setup — no dependencies to install manually
- ✅ Settings persistence (remember last folder)
- ✅ Support: MP4, MKV, MOV, AVI, JPG, PNG, WebP, etc.

#### Algorithm
- Reverse alpha blending: `J = (I - α·255) / (1 - α)`
- Temporal median across 20 frames isolates static watermark
- Tophat + inpainting estimates clean background
- Per-pixel alpha recovery + edge blurring for smooth removal

#### Tech Stack
- **Backend**: Flask, OpenCV, numpy, ffmpeg-imageio
- **Frontend**: Vanilla JS, CSS Glass-morphism design
- **Deployment**: Local Windows batch file, no cloud required

---

**[Unreleased]**
- [ ] Batch processing (select multiple files)
- [ ] Video scrubber (preview different parts)
- [ ] Keyboard shortcuts (Delete=clear, Enter=preview)
- [ ] Undo/Reset selection
- [ ] Save/Load session (bbox + settings)
- [ ] Dark/light theme toggle
- [ ] .exe installer (pyinstaller)
- [ ] macOS/Linux support

---

**Notes:**
- All versions maintain 100% local processing — no cloud uploads
- Settings stored in `settings.json` (user's folder path)
- Cache cleared on each server restart
