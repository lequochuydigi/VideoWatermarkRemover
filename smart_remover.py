import cv2
import numpy as np


class SmartWatermarkRemover:
    """
    Smart watermark removal using REVERSE ALPHA BLENDING.

    A semi-transparent watermark (e.g. the white "Veo" / VieON star) is composited
    onto every frame as:

        I = (1 - alpha) * J + alpha * W

    where I is the observed frame, J is the true (clean) frame, alpha is the
    per-pixel transparency matte, and W is the watermark colour (white = 255).

    Because the watermark is STATIC over time while the background MOVES, and
    because its colour is known (white), we can estimate the alpha matte once and
    then RECOVER the original pixels for every frame:

        J = (I - alpha * W) / (1 - alpha)

    This preserves the moving background underneath the watermark instead of
    hallucinating/inpainting it, giving a far cleaner result with no smudge and
    no temporal flicker. Fully-opaque pixels (alpha ~ 1, rare for Veo) cannot be
    recovered and fall back to Telea inpainting.
    """

    def __init__(self, sensitivity='medium'):
        self.sensitivity = sensitivity
        self.alpha = None            # float32 (h, w), per-pixel transparency 0..1
        self.opaque_mask = None      # uint8  (h, w), pixels too opaque to recover
        self.feather_mask = None     # float32 (h, w), 0..1 confined region
        self.despill = 0.0           # 0..1 strength to remove leftover white specks
        self.edge_blur = 0           # px kernel for soft glow blur over the region
        self.stats = {}

        # Number of frames sampled across the video to build the alpha matte.
        self.max_frames_to_analyze = 30

        # Sensitivity presets: (alpha gain, alpha floor, tophat threshold)
        # Floors are low so the faint halo around the mark is kept (not cut off)
        # and removed by un-blending instead of leaving a shadow.
        self._presets = {
            'low':    (0.85, 0.025, 12),
            'medium': (1.00, 0.015, 8),
            'high':   (1.20, 0.010, 6),
        }

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _odd(v):
        v = int(v)
        if v < 3:
            return 3
        return v if v % 2 == 1 else v + 1

    def _tophat_kernel(self, h, w):
        # White tophat extracts bright structures (the whole watermark body,
        # solid centre included) smaller than the kernel. Size it a bit larger
        # than the watermark, i.e. relative to the ROI, but bounded.
        k = self._odd(int(min(h, w) * 0.8))
        k = max(21, min(k, 45))
        k = min(k, self._odd(min(h, w) - 2))
        return max(3, k)

    def _feather_iter(self, h, w):
        # How far to grow the user's shape outward to also catch the surrounding
        # halo (a few px, scaled to the ROI size, kept small to avoid touching
        # genuinely clean background far from the mark).
        return max(2, min(5, int(round(min(h, w) * 0.08))))

    # ----------------------------------------------------------------- analyze
    def analyze(self, video_path, bbox, roi_mask=None,
                gain=None, floor=None, edge_expand=None, tophat_thr=None,
                despill=None, edge_blur=None):
        """
        Estimate the watermark alpha matte from the ROI.

        bbox is (x1, y1, x2, y2) in original video coordinates.
        roi_mask (optional) is a full-frame uint8 image (255 inside the shape the
        user selected). The estimated alpha is confined to this shape, but the
        shape is first feathered outward a few pixels so the halo just outside
        the drawn outline is also removed. If None, the whole bbox is used.

        gain / floor / edge_expand / tophat_thr (optional) override the
        sensitivity preset so the UI sliders can tune removal per video:
          - gain: multiplier on the alpha matte (>1 removes more aggressively)
          - floor: alpha values below this are zeroed (lower = more coverage)
          - edge_expand: px the shape grows outward to catch the halo
          - tophat_thr: brightness threshold to detect the watermark body
        """
        x1, y1, x2, y2 = [int(v) for v in bbox]
        if x2 <= x1 or y2 <= y1:
            raise Exception("Invalid bounding box")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise Exception("Cannot open video for analysis")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        if total_frames <= 0:
            total_frames = 300

        step = max(1, total_frames // self.max_frames_to_analyze)

        # Sequential read with grab()-skip is much faster than seeking for H.264
        # (seeking requires finding keyframe + decoding forward; grab just advances)
        crops = []
        frame_idx = 0
        while len(crops) < self.max_frames_to_analyze:
            if frame_idx % step == 0:
                ret, frame = cap.read()
                if not ret:
                    break
                crops.append(frame[y1:y2, x1:x2].astype(np.float32))
            else:
                if not cap.grab():
                    break
            frame_idx += 1
        cap.release()

        if len(crops) < 3:
            raise Exception("Not enough frames to analyze")

        p_gain, p_floor, p_thr = self._presets.get(self.sensitivity,
                                                   self._presets['medium'])
        gain = p_gain if gain is None else float(gain)
        floor = p_floor if floor is None else float(floor)
        th_thr = p_thr if tophat_thr is None else float(tophat_thr)

        crops_arr = np.array(crops, dtype=np.float32)   # (N, h, w, 3) BGR
        h, w = crops_arr.shape[1:3]

        # 0. Feathered shape mask (0..1): the user-selected shape grown outward a
        #    few px so the surrounding halo is also un-blended, with a soft edge.
        if roi_mask is not None:
            shape_crop = roi_mask[y1:y2, x1:x2]
            if shape_crop.shape[:2] != (h, w):
                shape_crop = cv2.resize(shape_crop, (w, h),
                                        interpolation=cv2.INTER_NEAREST)
            it = self._feather_iter(h, w) if edge_expand is None else int(edge_expand)
            it = max(0, it)
            if it > 0:
                grown = cv2.dilate(shape_crop, np.ones((3, 3), np.uint8),
                                   iterations=it)
            else:
                grown = shape_crop.copy()
            feather = cv2.GaussianBlur(grown.astype(np.float32) / 255.0,
                                       (0, 0), sigmaX=max(1.0, it / 1.5))
            feather = np.clip(feather, 0.0, 1.0)
        else:
            feather = np.ones((h, w), dtype=np.float32)

        # 1. Temporal median: removes the moving background, keeps the static
        #    watermark (and the average background underneath it).
        M = np.median(crops_arr, axis=0)                # (h, w, 3) float32
        M_u8 = np.clip(M, 0, 255).astype(np.uint8)

        # 2. Estimate the clean background that lies UNDER the watermark.
        #    White tophat extracts the full bright watermark (solid centre too),
        #    which is then inpainted away, so B holds background detail elsewhere.
        gray = cv2.cvtColor(M_u8, cv2.COLOR_BGR2GRAY)
        k = self._tophat_kernel(h, w)
        kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kern)
        rough = (tophat > th_thr).astype(np.uint8) * 255
        # Grow the detected footprint generously so the clean-background estimate
        # B also spans the halo region -> alpha then captures the halo gradient.
        rough = cv2.dilate(rough, np.ones((3, 3), np.uint8), iterations=3)

        if np.any(rough):
            B = cv2.inpaint(M_u8, rough, 3, cv2.INPAINT_TELEA).astype(np.float32)
        else:
            B = M.copy()

        # 3. Alpha matte from the white-colour prior:
        #       I = (1-a) J + a*255  ->  a = (M - B) / (255 - B)
        eps = 1e-6
        alpha3 = (M - B) / (255.0 - B + eps)
        alpha = np.clip(alpha3.mean(axis=2), 0.0, 0.98)

        # 4. Apply sensitivity, drop noise, keep edges soft (a soft matte handles
        #    the faint halo gradually, so no hard dilation / no blob).
        alpha = np.clip(alpha * gain, 0.0, 0.98)
        alpha[alpha < floor] = 0.0
        alpha = cv2.GaussianBlur(alpha, (3, 3), 0)

        # Confine to the (feathered) user shape: zero outside, soft at the rim so
        # the halo just beyond the outline is still removed gradually.
        alpha = alpha * feather

        self.alpha = alpha.astype(np.float32)
        self.opaque_mask = ((alpha > 0.9) * 255).astype(np.uint8)
        self.feather_mask = feather.astype(np.float32)
        self.despill = 0.0 if despill is None else float(despill)
        self.edge_blur = 0 if edge_blur is None else int(edge_blur)

        # 5. Stats for the UI.
        wm = alpha > floor
        wm_count = int(np.count_nonzero(wm))
        static_pct = wm_count / alpha.size * 100.0
        trans_pct = (np.count_nonzero(wm & (alpha < 0.6)) / alpha.size) * 100.0
        alpha_mean = float(alpha[wm].mean()) if wm_count > 0 else 0.0

        self.stats = {
            'static_percent': round(static_pct, 1),
            'transition_percent': round(trans_pct, 1),
            'dynamic_percent': round(100.0 - static_pct, 1),
            'alpha_mean': round(alpha_mean, 3),
            'watermark_color': [255.0, 255.0, 255.0],
        }
        return self.stats

    # ------------------------------------------------------------- process_frame
    def process_frame(self, frame_rgb):
        """
        Un-blend the watermark out of a single frame (ROI crop).

        White is (255,255,255) in both RGB and BGR, and the alpha matte is a
        per-pixel scalar, so this is colour-order agnostic.
        """
        if self.alpha is None:
            return frame_rgb

        h, w = frame_rgb.shape[:2]
        a = self.alpha
        if a.shape[:2] != (h, w):
            a = cv2.resize(a, (w, h), interpolation=cv2.INTER_LINEAR)

        a3 = a[..., None]
        f = frame_rgb.astype(np.float32)

        # J = (I - alpha*255) / (1 - alpha)
        recovered = (f - a3 * 255.0) / (1.0 - a3 + 1e-6)
        out = np.clip(recovered, 0, 255).astype(np.uint8)

        # Fallback: pixels too opaque to recover -> inpaint the few that remain.
        if self.opaque_mask is not None and np.any(self.opaque_mask):
            om = self.opaque_mask
            if om.shape[:2] != (h, w):
                om = cv2.resize(om, (w, h), interpolation=cv2.INTER_NEAREST)
            out = cv2.inpaint(out, om, 3, cv2.INPAINT_TELEA)

        # Feather mask resized to this frame (used by de-spill and edge blur).
        fm = self.feather_mask
        if fm is not None and fm.shape[:2] != (h, w):
            fm = cv2.resize(fm, (w, h), interpolation=cv2.INTER_LINEAR)

        # De-spill: actively remove the leftover white specks/ring that the
        # alpha matte underestimated. Detect pixels still brighter than their
        # local neighbourhood inside the region, then inpaint them away.
        if self.despill > 0 and fm is not None:
            inside = fm > 0.01
            if np.any(inside):
                gray = cv2.cvtColor(out, cv2.COLOR_RGB2GRAY).astype(np.float32)
                local = cv2.cvtColor(cv2.medianBlur(out, 5),
                                     cv2.COLOR_RGB2GRAY).astype(np.float32)
                resid = gray - local
                thr = 12.0 - 10.0 * float(np.clip(self.despill, 0, 1))
                spill = ((resid > thr) & inside).astype(np.uint8) * 255
                if np.any(spill):
                    spill = cv2.dilate(spill, np.ones((3, 3), np.uint8), 1)
                    out = cv2.inpaint(out, spill, 3, cv2.INPAINT_TELEA)

        # Edge blur / soft glow: blend a blurred copy into the region, weighted
        # by the feather mask, to smooth the rim and hide faint residue.
        if self.edge_blur and self.edge_blur > 0 and fm is not None:
            k = int(self.edge_blur) | 1
            blurred = cv2.GaussianBlur(out, (k, k), 0)
            wgt = (fm * float(np.clip(self.edge_blur / 25.0, 0, 1)))[..., None]
            out = (out.astype(np.float32) * (1.0 - wgt) +
                   blurred.astype(np.float32) * wgt)
            out = np.clip(out, 0, 255).astype(np.uint8)

        return out
