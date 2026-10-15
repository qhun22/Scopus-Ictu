# Báo cáo khắc phục CI: guard cổng 5432 chặn nhầm PostgreSQL container của GitHub Actions

**Ngày:** 2026-10-12
**Trạng thái:** HEAD mới nhất (`89cf46f`) có CI **PASS** — cả Backend và Frontend.

---

## 1. Link GitHub Actions run cũ bị lỗi

- `cdaf8cf`: https://github.com/qhun22/Scopus-Ictu/actions/runs/38195044791
- `7b13d2d` (HEAD lúc nhận email): https://github.com/qhun22/Scopus-Ictu/actions/runs/38195491434

Cả hai đều fail ở job **Backend (Python)**, bước **Run tests**. Job **Frontend (Node)** PASS ở mọi run trong toàn bộ quá trình điều tra — không có vấn đề gì ở frontend.

## 2. Nguyên nhân gốc — có bằng chứng, không suy đoán

Lấy log chi tiết (`gh run view --log`) của cả 2 run, không kết luận từ email/annotation. Tìm được 2 test thực sự fail (phần còn lại là log PostgreSQL ghi nhận lỗi ràng buộc — hành vi **mong đợi** của các test khác đang cố tình kiểm tra constraint vi phạm):

```
FAILED tests/integration/test_generate_matching_candidates_cli.py::test_guards_reject_wrong_database_port_5432_and_repo_manifest
FAILED tests/integration/test_generate_matching_candidates_cli.py::test_main_dry_run_and_apply_end_to_end
```

Đã xác minh file `backend/scripts/generate_matching_candidates.py` (công cụ vận hành CLI, không phải code web app) **không tồn tại** ở lần CI PASS gần nhất trước đó (`6b84f1a`) — đây là lần đầu tiên code này chạy qua CI, vì nhánh gốc tạo ra nó (`m27a/candidate-generation`) chưa từng trigger workflow (`gh run list --branch m27a/candidate-generation` → rỗng). **Không phải lỗi hồi quy do cleanup Git** — là code hợp lệ lần đầu chạm CI.

### Lớp nguyên nhân thứ nhất (đã sửa, chưa đủ)

CLI có `FORBIDDEN_PORTS = frozenset({5432})` — chặn cứng cổng 5432 để tránh ai đó vô tình chạy công cụ ghi dữ liệu nhắm vào PostgreSQL production/demo trên máy dev (luôn ở 5432 theo quy ước dự án). CI dùng PostgreSQL service container mặc định đúng cổng 5432 → trùng số, bị chặn nhầm dù là container ephemeral, vô hại.

**Sửa lần 1:** đổi cổng CI sang 5433 (`.github/workflows/ci.yml`). Chưa đủ — PostgreSQL bên trong container vẫn tự bind 5432 (chỉ Docker port-mapping phía host đổi), `inet_server_port()` vẫn báo 5432.

**Sửa lần 2:** thêm `PGPORT: "5433"` vào service container để PostgreSQL *thực sự* lắng nghe 5433 bên trong, khớp health-check và `TEST_DATABASE_URL`.

### Lớp nguyên nhân thứ hai (nguyên nhân gốc thật sự)

Sau khi cổng đã khớp, lỗi đổi sang **`server is not bound to loopback`** — guard thứ hai trong cùng hàm (`verify_server_identity`) kiểm tra `inet_server_addr() in {"127.0.0.1", "::1"}`. Trên kiến trúc GitHub Actions service container, PostgreSQL nhận kết nối qua mạng cầu (bridge) Docker riêng; dù client gọi qua `localhost`, server tự báo địa chỉ container nội bộ (dải `172.x.x.x`), không phải loopback literal. **Đây là giới hạn kiến trúc thật sự của GitHub Actions, không sửa được bằng cấu hình YAML** — phải sửa logic guard.

## 3. File đã sửa

| File | Nội dung thay đổi |
|---|---|
| `.github/workflows/ci.yml` | Đổi cổng PostgreSQL service sang 5433 (`PGPORT`, port mapping, health-check, mọi `DB_PORT`/`TEST_DATABASE_URL`); thêm biến `MATCHING_CLI_CI_CONTAINER_NETWORK=1` |
| `backend/scripts/generate_matching_candidates.py` | Thêm cơ chế mở rộng guard loopback có kiểm soát chặt (xem mục dưới) |
| `backend/tests/integration/test_generate_matching_candidates_cli.py` | Sửa 1 call site thiếu `environment=`; thêm 8 test mới cho cơ chế mở rộng |

### Thiết kế cơ chế mở rộng guard (theo đúng yêu cầu: không dựa 1 biến đơn lẻ)

`verify_server_identity()` chỉ chấp nhận địa chỉ server **không phải loopback literal** khi **đồng thời cả 3 điều kiện**:

1. Biến môi trường `MATCHING_CLI_CI_CONTAINER_NETWORK=1` được đặt **tường minh, đúng giá trị `"1"`** (không chấp nhận `"true"`/`"yes"` — đã có test riêng xác nhận).
2. `ENVIRONMENT` đúng bằng `"test"` (không bao giờ `"local"`/`"prod"`).
3. Địa chỉ server báo về **thực sự nằm trong dải mạng cầu Docker mặc định** (`172.16.0.0/12`, RFC 1918) — không phải "chấp nhận bất kỳ địa chỉ không-loopback nào". Một địa chỉ public thật (đã test bằng `203.0.113.7`, TEST-NET-3) vẫn bị từ chối dù cờ CI được bật.

Toàn bộ guard khác (tên database khớp `--expected-database`, database không nằm trong `FORBIDDEN_DATABASES`, cổng 5432 luôn bị cấm vô điều kiện, cổng khớp `--expected-port`) **giữ nguyên không đổi** — đã có test xác nhận riêng (`test_verify_server_identity_still_enforces_database_port_and_user_with_override`).

### 8 test mới (class `TestCiContainerLoopbackOverride`)

| Test | Kịch bản |
|---|---|
| `test_plain_loopback_always_allowed` | Loopback luôn PASS, có/không override |
| `test_docker_bridge_address_blocked_without_override` | Địa chỉ Docker bridge bị chặn khi KHÔNG có override |
| `test_docker_bridge_address_allowed_with_override` | Địa chỉ Docker bridge được chấp nhận khi có override |
| `test_public_address_blocked_even_with_override` | Địa chỉ public thật vẫn bị chặn dù override bật (không phải "chấp nhận mọi non-loopback") |
| `test_override_requires_both_flag_and_test_environment` | Cần cả 2: flag + `ENVIRONMENT=test` |
| `test_override_never_active_outside_test_environment` | Override không kích hoạt ở `local`/`prod` dù flag bật |
| `test_flag_set_to_non_one_value_does_not_activate_override` | Giá trị cờ lỏng lẻo (`"true"`) không kích hoạt — chỉ đúng `"1"` |
| `test_verify_server_identity_still_enforces_database_port_and_user_with_override` | Override không làm yếu guard database/port khác, chạy thật trên DB test cô lập |

## 4. Commit SHA mới

| SHA | Nội dung |
|---|---|
| `3eaea1e` | Sửa lần 1 (chỉ đổi port mapping — chưa đủ, vẫn fail) |
| `026fbf8` | Sửa lần 2 (`PGPORT` để PostgreSQL bind đúng 5433 — hết lỗi port, lộ ra lỗi loopback) |
| `89cf46f` | **Sửa đúng nguyên nhân gốc** — cơ chế mở rộng guard loopback có kiểm soát chặt, kèm 8 test mới |

Cả 3 đều push fast-forward lên `origin/main`, không force-push, không đụng `refs/agents`/stash/backup/App DB/teacher DB/`/system/reset`.

## 5. Kết quả test cục bộ (trên DB test cô lập `scopus_ictu_test_pytest_20261011`, cổng 55432)

| Hạng mục | Kết quả |
|---|---|
| `test_generate_matching_candidates_cli.py` riêng | **20 passed** (12 cũ + 8 mới) |
| Toàn bộ backend suite | **883 passed, 5 skipped, 0 failed** |
| Alembic | `f6a1b2c3d4e5 (head)` |
| Frontend typecheck + build | **PASS** |

## 6. Link GitHub Actions run mới (PASS)

https://github.com/qhun22/Scopus-Ictu/actions/runs/38197696903 — HEAD `89cf46f`

## 7. Kết quả Backend / Frontend trên CI thật

| Job | Bước | Kết quả |
|---|---|---|
| Backend (Python) | Initialize containers | success |
| Backend (Python) | Alembic upgrade | success |
| Backend (Python) | **Run tests** | **success — 883 passed, 5 skipped, 0 failed** (log lấy trực tiếp từ GitHub Actions, không phải kết quả local) |
| Frontend (Node) | Build | success |

## 8. Còn lỗi hoặc cảnh báo không

- **0 lỗi.** `conclusion: success` cho cả 2 job.
- Cảnh báo không chặn: `PydanticDeprecatedSince20` (class-based Config, đã biết từ trước, ngoài phạm vi sửa lỗi CI này), `InsecureKeyLengthWarning` (JWT test fixture dùng secret ngắn có chủ đích cho test), `StarletteDeprecationWarning` (HTTP status alias). Không liên quan tới thay đổi trong phiên này.
- Frontend: 1 cảnh báo chunk-size (tối ưu hiệu năng, không phải lỗi) — đã tồn tại từ trước.

---

**Chưa tự chuyển repository sang PUBLIC** — điều kiện PR/cache và các mục khác trong kế hoạch PUBLIC trước đó chưa được xác nhận lại trong phiên này, đúng theo yêu cầu dừng ở chỗ CI đã xác nhận PASS. `main` cục bộ ở worktree chính (`D:\...\Scopus-Ictu`) **vẫn chưa đồng bộ** với `origin/main` mới (`89cf46f`) — không tự ý `reset --hard` lần này (đã bị hệ thống chặn một lần trước đó, chưa có chỉ thị mới để thử lại); lệnh an toàn để tự đồng bộ đã ghi ở báo cáo [GITHUB_FINAL_HANDOVER_20261012.md](./GITHUB_FINAL_HANDOVER_20261012.md) mục F.
