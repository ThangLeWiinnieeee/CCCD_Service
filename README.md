# WebTutorCenter CCCD Service

Microservice tự host để đọc và kiểm tra tính nhất quán của CCCD Việt Nam bằng OpenCV,
PaddleOCR và QR. Service không lưu ảnh và không khẳng định giấy tờ là thật do cơ quan nhà
nước cấp; kết quả dùng để hỗ trợ quy trình admin duyệt hồ sơ.

## Chức năng

- Từ chối file sai định dạng, quá lớn hoặc ảnh có số pixel vượt giới hạn.
- Kiểm tra độ phân giải, độ mờ, sáng tối, lóa và khả năng tìm thấy thẻ.
- Cắt, xoay và hiệu chỉnh phối cảnh bằng OpenCV.
- OCR tiếng Việt bằng PaddleOCR chạy local.
- Đọc QR mặt trước và đối chiếu với OCR/thông tin người khai.
- Trả `pass`, `retake`, `review` hoặc `suspicious` cùng mã lý do.

## Chạy bằng Docker

```bash
docker build -t webtutorcenter-cccd ./cccd-service
docker run --rm -p 8002:8002 \
  -e CCCD_INTERNAL_SECRET=change-me \
  webtutorcenter-cccd
```

Docker mặc định tải model vào image trong lúc build để lúc chạy không cần tải lại. Khi chỉ
muốn kiểm tra nhanh Dockerfile mà chưa tải model:

```bash
docker build --build-arg PRELOAD_MODELS=false -t webtutorcenter-cccd ./cccd-service
```

Model sẽ được tải ở request OCR đầu tiên nếu bỏ qua preload.

Kiểm tra service:

```bash
curl http://localhost:8002/health
```

## Chạy local

PaddlePaddle chưa hỗ trợ đồng đều mọi bản Python mới; dùng Python 3.11 hoặc 3.12.

```bash
cd cccd-service
python -m venv .venv
.venv/Scripts/activate
python -m pip install -e ".[dev]"
uvicorn cccd_service.main:app --host 0.0.0.0 --port 8002
```

Trên Linux/macOS, lệnh kích hoạt môi trường là `source .venv/bin/activate`.

## API

`POST /api/verify` dùng `multipart/form-data`:

- `front`: ảnh mặt trước, bắt buộc.
- `back`: ảnh mặt sau, bắt buộc.
- `claimed_full_name`: họ tên người khai, tùy chọn.
- `claimed_date_of_birth`: ngày sinh dạng `YYYY-MM-DD`, tùy chọn.
- `claimed_gender`: `male`/`female`, tùy chọn.
- Header `X-Internal-Secret`: bắt buộc khi `CCCD_INTERNAL_SECRET` được cấu hình.

Ví dụ:

```bash
curl -X POST http://localhost:8002/api/verify \
  -H "X-Internal-Secret: change-me" \
  -F "front=@front.jpg" \
  -F "back=@back.jpg" \
  -F "claimed_full_name=Nguyễn Văn An" \
  -F "claimed_date_of_birth=2004-02-01" \
  -F "claimed_gender=male"
```

Swagger UI có tại `http://localhost:8002/docs`.

## Kiểm tra code

```bash
pytest
ruff check .
```

Không đặt ảnh CCCD thật trong `tests/`. Chỉ dùng ảnh tổng hợp, ảnh đã che dữ liệu hoặc thư
mục `tests/fixtures/private/` đã được gitignore.
