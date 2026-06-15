# Auto Video & Image Watermark Eraser

Xóa watermark VEO 3 / Veo Omni khỏi video và ảnh bằng Reverse Alpha-Blending. Không cần cài đặt thủ công — chỉ cần chạy `run.bat` là bạn có giao diện web trên chính máy bạn để sử dụng.

---

## Về tác giả: Lê Quốc Huy Digi

1. Chào các bạn mình là **Lê Quốc Huy** hay thường viết tắt là **Huy Digi**
2. Mình chuyên triển khai các dự án web Wordpress, PHP từ 2016 và chuyển sang phát triển các Workflow Automation như n8n và ứng dụng với AI từ 2025
3. Theo dõi kênh Youtube của mình để không bỏ lỡ những update & thủ thuật công nghệ thông tin & AI mới nhất từ mình nhé 👉 [https://www.youtube.com/@huydigi](https://www.youtube.com/@huydigi)
4. Bạn có thể inbox cho mình tại Facebook, ae cafe giao lưu tại Hà Nội 👉 [https://www.facebook.com/lequochuydigi/](https://www.facebook.com/lequochuydigi/)

---

## Cài đặt & Khởi động (Windows)

1. **Tải về** và giải nén
2. Đảm bảo đã cài **Python 3.10+** — [tải tại đây](https://www.python.org/downloads/)  
   ⚠️ Nhớ tick **"Add Python to PATH"** khi cài đặt
3. Double-click **`run.bat`**

Script sẽ tự động:
- Tạo môi trường ảo `.venv`
- Cài thư viện từ `requirements.txt`
- Mở trình duyệt tại `http://localhost:5000`

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

1. Mở `http://localhost:5000`
2. **Chọn thư mục** chứa video/ảnh bằng nút thư mục hoặc gõ đường dẫn trực tiếp
3. Chọn file từ danh sách (hiển thị badge **VID** / **IMG**)
4. Vẽ vùng watermark trên canvas (Vuông / Thoi / Tròn / Custom lasso)
5. Chọn phương thức và tinh chỉnh slider → xem Before/After preview
6. Bấm **Bắt đầu xóa** → file output lưu cùng thư mục gốc

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
