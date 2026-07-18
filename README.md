# License Integrity Auditor

Công cụ desktop (PySide6) kiểm tra **thực chất** tình trạng bản quyền
Windows / Office trên máy tính — kể cả khi hệ thống hiển thị
`"Activated"` / `"Đã kích hoạt"`.

## Vì sao cần công cụ này?

`slmgr /xpr` hay hộp thoại **Settings → Activation** có thể báo *"Windows
is activated"* ngay cả khi máy đang dùng các công cụ giả lập kích hoạt
(KMS emulator, HWID activation script, patch loader...). Bản thân các
công cụ đó thao túng registry/scheduled task/service để hệ thống *tưởng*
là đã có bản quyền hợp lệ. Công cụ này đối chiếu **nhiều nguồn dữ liệu độc
lập** để phát hiện sự bất nhất đó.

## Các hạng mục kiểm tra

| # | Hạng mục | Nguồn dữ liệu |
|---|----------|---------------|
| 1 | Kích hoạt Windows | `slmgr.vbs /dli`, `/xpr` — License Status, kênh cấp phép (Retail/OEM/Volume) |
| 2 | Kích hoạt Office | `ospp.vbs /dstatus` |
| 3 | Khóa OEM trong BIOS | `SoftwareLicensingService.OA3xOriginalProductKey` (bảng ACPI MSDM) |
| 4 | Dấu vết Registry | Uninstall keys, Run keys, Services, cờ `SkipRearm`... đối chiếu với danh sách nhận diện công cụ kích hoạt phổ biến |
| 5 | Scheduled Task | `schtasks /query /v` — tác vụ lạ dùng để tự động rearm/gia hạn |
| 6 | Windows Services | `sc query` — service giả lập KMS nội bộ hoặc hook SPP |
| 7 | Tàn dư file/thư mục | Quét nông (2 cấp) các thư mục hệ thống phổ biến |

Kết quả tổng hợp thành 1 trong 3 kết luận: **BẢN QUYỀN HỢP LỆ**, **NGHI
VẤN** hoặc **VI PHẠM BẢN QUYỀN**, kèm điểm rủi ro 0–100 và bằng chứng chi
tiết cho từng hạng mục.

> Công cụ chỉ **đọc** thông tin hệ thống để chẩn đoán — không chỉnh sửa,
> gỡ, hay vô hiệu hoá bất kỳ thành phần nào.

## Cài đặt

```bash
pip install -r requirements.txt
```

Yêu cầu: Windows 10/11, Python 3.10+. Nên chạy với quyền **Administrator**
để đọc đầy đủ registry (HKLM\SYSTEM\...) và khóa OEM trong BIOS.

## Chạy ứng dụng

```bash
python main.py
```

## Giao diện

- Dark theme chuẩn Enterprise, dùng PySide6 + QSS.
- **Ẩn thanh tiêu đề mặc định của Windows** (Frameless Window), thay bằng
  Custom Title Bar tự vẽ (kéo-thả di chuyển, minimize/maximize/close
  riêng, double-click để phóng to).
- Cửa sổ bo góc + đổ bóng (drop shadow), nền trong suốt.
- Hộp thoại chi tiết & xác nhận đều là **modal tự dựng** (overlay phủ
  trong cửa sổ chính), không dùng `QDialog`/`QMessageBox` gốc của OS.
- Vùng nội dung cuộn được nhưng **ẩn thanh cuộn** (vẫn cuộn bằng chuột/
  trackpad bình thường).
- Xuất báo cáo JSON chi tiết qua nút "Xuất báo cáo".

## Cấu trúc dự án

```
license_auditor/
├── main.py
├── requirements.txt
├── app/
│   ├── core/
│   │   ├── detectors.py   # toàn bộ logic dò quét
│   │   └── scanner.py     # QThread chạy quét nền, không đơ UI
│   ├── ui/
│   │   ├── title_bar.py   # custom title bar
│   │   ├── modal.py       # modal overlay tự dựng
│   │   ├── widgets.py     # ResultCard, VerdictBanner, Badge
│   │   └── main_window.py # cửa sổ chính
│   └── resources/
│       └── style.qss      # dark theme
```

## Giới hạn

- Chỉ chạy đầy đủ chức năng trên Windows (các script gọi `slmgr.vbs`,
  `ospp.vbs`, `winreg`, `schtasks`, `sc`, PowerShell CIM).
- Trên macOS/Linux, ứng dụng vẫn mở được để xem giao diện nhưng các thẻ
  kết quả sẽ báo "Chỉ hỗ trợ trên Windows".
- Danh sách nhận diện (registry/service/file signatures) mang tính tham
  khảo dựa trên các mẫu công cụ kích hoạt phổ biến; các phiên bản mới có
  thể đổi tên để né tránh, nên công cụ nên được cập nhật định kỳ.
