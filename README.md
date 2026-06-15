# Antigravity Watermark Eraser

Web app xóa watermark VEO / VieON khỏi video bằng **Reverse Alpha-Blending** — tái tạo nền gốc dưới watermark thay vì inpaint/blur, cho kết quả sạch và không có temporal flicker.

## Tính năng

- **Reverse alpha-blending** (Smart) — un-blend watermark bán trong suốt, bảo toàn nền chuyển động
- **Inpaint** — Telea inpainting
- **Blur** — làm mờ Gaussian
- Vẽ vùng chọn: **Vuông · Thoi · Tròn · Custom lasso**
- **Zoom/pan** ảnh preview để khoanh chính xác
- Before/After preview trực tiếp trước khi xử lý toàn video
- Thanh chỉnh: gain, floor, edge expand, tophat threshold, de-spill, glow/edge blur

## Yêu cầu

- Python ≥ 3.10
- ffmpeg (có trong PATH hoặc tự động dùng `imageio-ffmpeg`)

## Cài đặt

```bash
git clone <repo-url>
cd watermark_remover
pip install -r requirements.txt
```

## Sử dụng

1. Đặt file `.mp4` vào thư mục `videos/` (hoặc chỉ định thư mục khác bằng biến môi trường)
2. Khởi động server:

```bash
python app.py
```

3. Mở trình duyệt tại `http://localhost:5000`

## Cấu hình

| Biến môi trường | Mặc định | Mô tả |
|---|---|---|
| `VIDEOS_DIR` | `./videos` | Thư mục chứa video đầu vào và output |
| `HOST` | `localhost` | Host server |
| `PORT` | `5000` | Port server |
| `DEBUG` | `true` | Flask debug mode |

Ví dụ:

```bash
# Windows CMD
set VIDEOS_DIR=D:\MyVideos && python app.py

# PowerShell
$env:VIDEOS_DIR="D:\MyVideos"; python app.py

# Linux / macOS
VIDEOS_DIR=/home/user/Videos python app.py
```

## Cách thuật toán Smart hoạt động

Watermark VEO là ảnh trắng bán trong suốt, composite lên mỗi frame:

```
I = (1 - α) · J + α · 255
```

Vì watermark **tĩnh** còn nền **chuyển động**, temporal median qua ~30 frame tách được alpha matte.
Sau đó mỗi frame được un-blend:

```
J = (I - α · 255) / (1 - α)
```

Pixel quá opaque (α > 0.9) fallback về Telea inpaint.

## Cấu trúc

```
watermark_remover/
├── app.py              # Flask server + API endpoints
├── smart_remover.py    # Reverse alpha-blending algorithm
├── config.py           # Cấu hình (env vars)
├── requirements.txt
├── videos/             # Đặt .mp4 vào đây (gitignored)
├── previews/           # Ảnh preview tạm (gitignored)
├── templates/
│   └── index.html
└── static/
    ├── main.js
    └── index.css
```
