# 🔧 Troubleshooting Guide

## Vấn đề thường gặp & Cách khắc phục

---

## ❌ **"Analyze timeout hoặc codec lỗi"**

### 🔍 Nguyên nhân
- Video sử dụng codec **H.265 (HEVC), AV1, VP9** mà OpenCV không hỗ trợ tốt
- Video bị hỏng hoặc có format lạ (MKV with special streams, etc.)
- Server quá chậm hoặc RAM không đủ

### ✅ Cách sửa
1. **Thử lại lần 2** — tool sẽ tự retry với 8 frames thay vì 20 (nhanh hơn)
2. **Đổi phương thức**: thay vì "Smart AI" → thử "Blur" hoặc "Inpaint"
3. **Giảm nhạy cảm**: thử "Độ nhạy: Nhẹ" thay vì "Vừa"
4. **Convert video trước**:
   ```bash
   ffmpeg -i input.mkv -c:v libx264 -c:a aac output.mp4
   ```
5. **Report lỗi** — paste tên file + error message để mình cải thiện

---

## ❌ **"Không thể trích xuất khung hình"**

### ✅ Cách sửa
1. Kiểm tra file video có bị hỏng không:
   ```bash
   ffmpeg -v error -i video.mp4 -f null -
   ```
   Nếu có error → file bị hỏng

2. Thử mở video bằng **Windows Media Player** hoặc **VLC** — nếu không mở được thì tool cũng không thể

3. Đổi sang video khác để test

---

## ❌ **"Preview rất chậm (mất 5-10s)"**

### 🔍 Nguyên nhân
- Lần đầu preview → tool phải đọc 20 frame từ video (I/O chậm)
- Video lớn, độ phân giải cao, hoặc HDD chậm

### ✅ Cách sửa
1. **Lần đầu thì bình thường chậm** — Preview sau sẽ nhanh < 1 giây (đã cache)
2. **Kéo slider gain/floor/etc** → nhanh vì chỉ tính toán lại, không re-read frame
3. Nếu Preview **mãi mãi chậm**:
   - Kiểm tra HDD còn dung lượng không
   - Đóng những app khác tiêu tốn I/O (Spotify, OneDrive sync, etc.)
   - Thử chọn bbox nhỏ hơn (scope nhỏ → nhanh hơn)

---

## ❌ **"Kết quả xóa không sạch / còn vết logo"**

### ✅ Cách sửa
1. **Điều chỉnh slider**:
   - 🔴 Độ mạnh (Gain): tăng từ 1.0 → 1.5-2.0
   - 🟡 Độ phủ (Floor): tăng từ 0.015 → 0.03-0.05
   - 🟢 Mở rộng viền (Edge Expand): tăng từ 3 → 7-10
   - 🔵 Khử trắng dư (Despill): tăng từ 0 → 0.3-0.5

2. **Đổi phương thức**:
   - Logo màu trắng → thử "Smart" trước (phù hợp nhất)
   - Logo màu khác → thử "Inpaint"
   - Background phức tạp → thử "Blur"

3. **Chọn lại vùng**:
   - Vùng bbox phải **bao trọn toàn bộ logo** + 5-10px xung quanh
   - Không chọn quá to (bao gồm background → xóa nhầm)

4. **Test preview trước** khi render video toàn bộ

---

## ❌ **"Localhost k lên / ERR_CONNECTION_REFUSED"**

### 🔍 Nguyên nhân
- Cổng 8080 bị chiếm bởi ứng dụng khác
- Firewall chặn (hiếm)
- Python/Flask startup fail

### ✅ Cách sửa
1. **Check server log** — mở CMD từ thư mục app, chạy:
   ```bash
   python app.py
   ```
   Xem error message chi tiết

2. **Port bị chiếm?**:
   ```bash
   netstat -ano | findstr 8080
   ```
   Nếu có output → kill process đó hoặc đổi port trong `config.py`

3. **Firewall**:
   - Kiểm tra Windows Firewall có block Python không
   - Hoặc tắm Firewall tạm thời để test

4. **Khởi động lại**: Đóng CMD window, chạy lại `run.bat`

---

## ❌ **"Video/Ảnh không hiển thị trong danh sách"**

### ✅ Cách sửa
1. **Đổi thư mục**: Click nút "..." → chọn thư mục chứa video
2. **Check định dạng file**:
   - Video: `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm` (chữ thường)
   - Ảnh: `.jpg`, `.png`, `.webp`, `.bmp` (chữ thường)
3. **Đổi tên**: Xoá ký tự đặc biệt trong tên file (chỉ giữ chữ số + dấu gạch nối)
4. **Refresh**: Click nút rotate-right để làm mới danh sách

---

## ✅ **Mọi thứ chạy tốt không?**

Tuyệt vời! 🎉

- **Like & share** để hỗ trợ tác giả
- **Report issues** nếu gặp bug: [GitHub Issues](https://github.com/lequochuydigi/VideoWatermarkRemover/issues)
- **Request features** trên [Discussions](https://github.com/lequochuydigi/VideoWatermarkRemover/discussions)

---

**Version**: v2.0.0  
**Last updated**: 2026-06-18
