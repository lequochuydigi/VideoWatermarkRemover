# Antigravity Watermark Eraser | v2.0.0

**Xóa watermark VEO / VieON khỏi video & ảnh bằng Reverse Alpha-Blending. Chạy 100% offline trên máy bạn — miễn phí, không upload lên cloud.**

Công cụ sử dụng thuật toán tính ngược độ mờ (`alpha`) của watermark nửa trong suốt để khôi phục lại ảnh nền gốc — sạch hơn hẳn so với Blur/Inpaint thông thường.

---

## Về tác giả: Lê Quốc Huy Digi

1. Chào các bạn mình là **Lê Quốc Huy** hay thường viết tắt là **Huy Digi**
2. Mình chuyên triển khai các dự án web Wordpress, PHP từ 2016 và chuyển sang phát triển các Workflow Automation như n8n và ứng dụng với AI từ 2025
3. Theo dõi kênh Youtube của mình để không bỏ lỡ những update & thủ thuật công nghệ thông tin & AI mới nhất từ mình nhé 👉 [https://www.youtube.com/@huydigi](https://www.youtube.com/@huydigi)
4. Bạn có thể inbox cho mình tại Facebook, ae cafe giao lưu tại Hà Nội 👉 [https://www.facebook.com/lequochuydigi/](https://www.facebook.com/lequochuydigi/)

---

## Cài đặt & Khởi động (Windows)

1. **Tải về** và giải nén
2. Cài **Python 3.11+** — [tải tại đây](https://www.python.org/downloads/)  
   ⚠️ Nhớ tick **"Add Python to PATH"** khi cài đặt
3. Double-click **`CLICK_VAO_DAY_DE_CHAY.bat`** (hoặc `run.bat`)

Script sẽ tự động:
- Tạo môi trường ảo `.venv`
- Cài thư viện từ `requirements.txt` (opencv, flask, numpy, ffmpeg)
- Mở trình duyệt tại `http://127.0.0.1:8080`

> ✅ Hỗ trợ: Python 3.11 / 3.12 / 3.13 / 3.14+  
> 💡 Tải Python 3.12: https://www.python.org/downloads/release/python-31210/

---

## Cài đặt (Linux / macOS)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

---

## Sử dụng

1. **Chọn Video/Ảnh** (Bước 1)
   - Chọn thư mục chứa file bằng nút thư mục hoặc gõ path
   - Click file từ danh sách

2. **Tùy chọn Xóa** (Bước 2)
   - Chọn hình dạng vùng: Vuông / Thoi / Tròn / Lasso tự do
   - Dùng Preset nếu watermark là VEO logo / VieON star
   - Hoặc Auto-detect (video only)
   - Chọn phương thức: **Smart AI** (khuyên dùng) / Inpaint / Blur

3. **Xử lý** (Bước 3)
   - Điều chỉnh Độ nhạy AI: Nhẹ / Vừa / Mạnh
   - Bấm **Tạo / Cập nhật Preview** → xem Before/After ngay
   - Kéo slider fine-tune (gain, floor, edge, etc.) → preview update < 0.5s (cached)
   - Bấm **BẮT ĐẦU XÓA WATERMARK** → video hoặc ảnh output

4. File output lưu với hậu tố `_no_watermark` cùng thư mục gốc

---

## 🆕 What's New in v2.0

- ⚡ **Timeout protection**: Analyze không treo nữa (30s timeout, auto-retry với 8 frames)
- 🎯 **ffmpeg frame extraction**: Replace cv2 → không bao giờ hung trên codec lạ (H.265, AV1, VP9)
- 🚀 **Speed**: First preview ~2-5s, slider changes <0.5s (temporal median cached)
- 🎨 **UI relaunch**: Horizontal 3-step bar (file → settings → process), canvas full height
- 🎚️ **Sensitivity toggle**: Low / Medium / High AI sensitivity buttons
- 📢 **Toast notifications**: Beautiful error messages (không alert box thô sơ)
- 📖 **[Troubleshooting guide](./TROUBLESHOOTING.md)**: Codec issues, timeouts, performance tips

---

## Tính năng

| | |
|---|---|
| **Smart (Reverse Alpha-Blend)** | Tái tạo nền gốc dưới watermark, không temporal flicker |
| **Inpaint** | Telea inpainting |
| **Blur** | Làm mờ Gaussian |
| **Hình dạng chọn vùng** | Vuông · Thoi · Tròn · Custom lasso |
| **Zoom/Pan canvas** | Phóng to để chọn vùng chính xác |
| **Before/After preview** | Live update khi kéo slider |
| **Ảnh tĩnh** | Hỗ trợ JPG, PNG, WebP, BMP |
| **Video** | MP4, MOV, AVI, MKV, WebM... |
| **Chọn thư mục** | Dialog chọn thư mục ngay trong UI |

---

## Cấu hình (tuỳ chọn)

```bat
:: Windows CMD
set VIDEOS_DIR=D:\MyVideos
run.bat
```

| Biến | Mặc định | Mô tả |
|---|---|---|
| `VIDEOS_DIR` | `~/Downloads` | Thư mục mặc định khi khởi động |
| `PORT` | `5000` | Port server |
| `HOST` | `localhost` | Host (set `0.0.0.0` để mở LAN) |

---

## Cấu trúc

```
watermark_remover/
├── run.bat             ← Chạy cái này để dùng (Windows)
├── app.py              ← Flask server
├── smart_remover.py    ← Thuật toán reverse alpha-blending
├── config.py           ← Đọc env vars
├── requirements.txt
├── templates/index.html
└── static/
    ├── main.js
    └── index.css
```
