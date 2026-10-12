# Ưu tiên 2 — ADMIN rà soát và hiệu chỉnh đơn vị có bằng chứng

**Ngày:** 2026-10-12
**Phạm vi:** ADMIN rà soát các vị trí tác giả chưa có đơn vị/mâu thuẫn/chỉ đối chiếu, bổ sung hiệu chỉnh có dẫn nguồn — lớp phủ hoàn toàn tách biệt khỏi dữ liệu Scopus gốc và kết quả đối chiếu tự động.

---

## 1. KIỂM TRA — hiện trạng trước khi làm

Khảo sát (agent Explore, trích path:line) phát hiện **quyết định kiến trúc quan trọng nhất của Ưu tiên 2**: bảng affiliation hiện có (`publication_author_affiliation_resolutions`/`_affiliations`) hoàn toàn không có chỗ cho hành động con người — không `created_by`, không `version`, và CHECK constraint `link_method` chỉ cho phép đúng 2 giá trị tự động (`ORCID_SCOPUS_ID_BRIDGE`, `POSITION_COUNT_NAME`), `link_status` của bảng affiliation con chỉ cho phép VERIFIED/CORROBORATED (không UNRESOLVED). Sửa trực tiếp các CHECK này có rủi ro cao đến 60+ test cũ.

**Quyết định (đã hỏi và được xác nhận):** bảng mới hoàn toàn riêng `publication_author_affiliation_overrides`, lớp phủ bên trên, **không bao giờ ghi vào** 2 bảng tự động — additive tuyệt đối, zero thay đổi lên CHECK constraint/schema cũ.

Pattern tái dùng tối đa từ khảo sát:
- Audit: `AuditEvent` (actor_invariant constraint, `before_state`/`after_state`/`reason` sẵn có) — tái dùng nguyên, action mới `AFFILIATION_OVERRIDE_CREATED/UPDATED/DELETED`.
- Optimistic lock tường minh: theo đúng mẫu `candidate_review_service.py` (`expected_version` client gửi, so sánh trước khi ghi) — không dùng SQLAlchemy `version_id_col` tự động vì cần kiểm soát lỗi rõ ràng hơn cho UI.
- RBAC: `require_role("ADMIN")`, theo đúng mẫu `affiliations.py` hiện có.
- API publication detail (`GET /publications/{eid}`) đã có sẵn cấu trúc `PublicationAuthorRead`/`AffiliationResolutionRead` — mở rộng thêm field `affiliation_override`, **phải tự thiết kế lại để không lộ UUID nội bộ** (phát hiện qua một test an toàn có sẵn từ trước, xem mục Lỗi #1).

## 2. THỰC HIỆN

### Thành phần mới
| File | Vai trò |
|---|---|
| `backend/app/models/affiliation_override.py` | Bảng `publication_author_affiliation_overrides`: 1 dòng = override hiện tại của 1 vị trí tác giả, `confidence` CHECK chỉ `CORROBORATED`/`UNRESOLVED` (không bao giờ VERIFIED) |
| `backend/alembic/versions/b5e8d2f1a4c7_...py` | Migration additive, test trên DB test, **chưa áp dụng App DB** |
| `backend/app/services/affiliation_override_service.py` | `list_needs_review()` (UNRESOLVED/CONFLICTING_SOURCES/LOW_CONFIDENCE), `upsert_override()` (tạo/sửa, optimistic lock, audit), `delete_override()` |
| `backend/app/api/v1/endpoints/affiliations.py` | +4 endpoint: `GET /needs-review`, `PUT /overrides/{id}`, `DELETE /overrides/{id}?expected_version=N` |
| `backend/app/schemas/publication_api.py`, `backend/app/services/publication_queries.py` | Thêm `AffiliationOverrideRead` **public-safe** (không ID nội bộ) vào `PublicationAuthorRead.affiliation_override` |
| `frontend/.../ManualReviewCard.tsx` (mới) | Card "4. Rà soát và hiệu chỉnh thủ công": danh sách cần rà soát, form sửa có pre-fill, xóa |
| `frontend/.../AuthorAffiliations.tsx` | Hiển thị override (box tím "ADMIN rà soát thủ công") trong publication detail, mọi role đọc được |

### Phân biệt rõ ADMIN rà soát vs. xác minh độc lập (yêu cầu mục 4)
- `confidence` CHECK ở cả model lẫn service **chỉ chấp nhận CORROBORATED/UNRESOLVED** — không có đường nào để một override trở thành VERIFIED, dù qua API hay ORM trực tiếp (xác nhận bằng test DB constraint, xem mục 3).
- Override **không đổi** `author.affiliation_status` (tính từ resolution tự động) — xác nhận bằng test (`test_override_never_appears_as_verified_in_affiliation_status`): tác giả UNRESOLVED ở tầng tự động vẫn hiển thị UNRESOLVED ở `affiliation_status`, override hiển thị **song song**, không hoà trộn.
- UI ghi rõ, không thể bỏ qua: mỗi override hiển thị kèm note cố định *"Entered by an ADMIN after manual review; not an independent identity verification. Never counted as VERIFIED."*

### Dữ liệu tối thiểu cho mỗi hiệu chỉnh (đúng yêu cầu)
`publication_author_id` (ngầm định qua URL) · đơn vị đề xuất (`affiliation_text`) · nguồn chứng cứ (`evidence_url`, bắt buộc) · lý do (`reason`, bắt buộc) · `created_by_user_id`/`updated_by_user_id` · `version` · `created_at`/`updated_at`. Giá trị trước/sau đầy đủ nằm trong `AuditEvent.before_state`/`after_state` của mỗi lần sửa — không mất lịch sử khi update.

### Không sửa Scopus raw, không xóa dấu vết nguồn trước đó
- `AffiliationImportService` (writer tự động) không import/tham chiếu bảng override ở bất kỳ đâu — xác nhận bằng grep và bằng test tích hợp chạy thật `AffiliationImportService().apply()` sau khi đã có override (`test_re_applying_automated_resolutions_never_touches_an_existing_override`): override giữ nguyên `version=1`, nội dung không đổi, trong khi 1 resolution tự động mới được thêm song song.
- `delete_override()` chỉ xóa đúng 1 dòng trong bảng override; xác nhận `publication_author_affiliation_resolutions` không đổi gì (test + xác nhận qua UI thật, xem mục 3).

## 3. KIỂM THỬ

### Bộ test tự động mới
`backend/tests/integration/test_affiliation_override_api.py` — **20/20 PASS**, bao gồm:

| Nhóm | Test case |
|---|---|
| RBAC | LECTURER/REVIEWER → 403 trên `needs-review` và `PUT override`; anonymous → 401 |
| Danh sách cần rà soát | UNRESOLVED/LOW_CONFIDENCE phân loại đúng; NOT_RECONCILED (chưa từng đối chiếu) nằm ngoài phạm vi |
| Tạo/sửa | Tạo thành công + audit before=null; thiếu `reason`/`evidence_url`/`affiliation_text` → 422; `confidence` không hợp lệ (vd gửi `VERIFIED`) → 422 với code `INVALID_CONFIDENCE`; vị trí tác giả không tồn tại → 404 |
| Optimistic lock | `expected_version` sai → 409 `STALE_OVERRIDE_VERSION`; **race condition thật**: 2 request tuần tự cùng base version 1, request 2 bị từ chối, dữ liệu của request 1 không bị ghi đè |
| Xóa | Xóa đúng, audit DELETED, resolution tự động bên dưới không đổi; version sai → 409; override không tồn tại → 404 |
| Hiển thị public-safe | `publication detail` chứa `affiliation_override` nhưng **không** lộ `publication_author_id` hay bất kỳ user UUID nào trong response |
| Không tự nâng VERIFIED | `affiliation_status` giữ nguyên UNRESOLVED dù đã có override CORROBORATED |
| Tương thích thu thập lại | Override giữ nguyên `version=1` sau khi chạy lại `AffiliationImportService().apply()` với payload mới cho cùng vị trí tác giả |
| DB constraint (defense in depth) | Insert trực tiếp ORM với `confidence='VERIFIED'` (bỏ qua toàn bộ validate của service) → `IntegrityError`, rollback sạch, 0 dòng sót lại |

### 2 bug thật phát hiện qua kiểm thử (không phải qua test tự động — qua UI thật với dữ liệu thật)

**Bug #1 — rò rỉ ID nội bộ (phát hiện bởi 1 test an toàn có sẵn từ Ưu tiên 1, `test_detail_serializes_no_internal_ids_and_uses_newest_version`):** thiết kế ban đầu đưa `publication_author_id` (UUID) thẳng vào `PublicationAuthorRead` — API này được LECTURER đọc được. Đã sửa: bỏ hẳn field này khỏi response public, và bỏ luôn `created_by_user_id`/`updated_by_user_id`/`id` khỏi `AffiliationOverrideRead` hiển thị trong publication detail (tạo 1 schema `OverrideRead` đầy đủ riêng, chỉ dùng cho API ADMIN `needs-review`/`PUT`/`DELETE`).

**Bug #2 — `AttributeError: 'UUID' object has no attribute 'publication_author_id'`, phát hiện qua UI thật (không có test tự động nào cover trước đó):** code gốc viết `{r.publication_author_id for r in db.scalars(select(...publication_author_id)).all()}` — `scalars()` trên 1 cột đã trả list UUID thuần, không phải object có attribute. Lỗi này **chỉ lộ ra khi đã có ít nhất 1 override tồn tại trong DB** trước khi gọi `needs-review` — toàn bộ 18 test ban đầu không cover đúng thứ tự thao tác này (chỉ test "trước khi có override" riêng). Đã sửa code và bổ sung 2 test chuyên biệt (`test_needs_review_still_works_after_an_override_was_created`, `test_needs_review_returns_full_override_for_prefilling_the_edit_form`) để chặn regression.

**Bug #3 (UX, phát hiện cùng lúc qua UI) — form hiệu chỉnh không pre-fill dữ liệu cũ:** API ban đầu chỉ trả `has_override: boolean`, không trả nội dung override hiện có, nên form luôn mở trống kể cả khi đã có hiệu chỉnh từ trước — ADMIN phải nhớ lại và gõ lại toàn bộ. Đã mở rộng `NeedsReviewItem`/`NeedsReviewItemRead` để trả kèm `override` đầy đủ, frontend dùng để pre-fill `affiliation_text`/`confidence`/`evidence_url` (riêng `reason` để trống có chủ đích — mỗi lần sửa cần lý do mới, không kế thừa lý do cũ).

### Kiểm thử qua trình duyệt thật (DB test cô lập, cổng 55432, database `scopus_ictu_test_pytest_20261011` — không phải App DB)

Toàn bộ luồng thực hiện qua UI thật (backend test cổng 8011, frontend test cổng 5183, tách biệt hoàn toàn 8001/5173 đang chạy App DB):

1. ADMIN đăng nhập (`qa.admin@ictu.edu.vn`) → vào "Chuẩn hóa dữ liệu" → tab "Đơn vị tác giả" → Card "4. Rà soát và hiệu chỉnh thủ công" hiển thị đúng 5/5 vị trí tác giả thật cần rà soát (dữ liệu kế thừa từ Ưu tiên 1: Hirsch, LeCun, Bengio, Hinton, Smith), đúng phân loại badge (UNRESOLVED/LOW_CONFIDENCE).
2. Bấm "Hiệu chỉnh" cho LeCun → điền "Meta AI Research (New York)", nguồn `https://ai.meta.com/people/yann-lecun/`, lý do → Lưu → toast "Đã lưu hiệu chỉnh" → DB xác nhận đúng dữ liệu, `version=1`.
3. Mở lại publication detail (`/publications/2-s2.0-TESTE2`) → box tím "ADMIN rà soát thủ công" hiển thị đúng dưới mục LeCun, **song song** với dữ liệu tự động (Facebook AI Research/New York University từ OpenAlex) — không ghi đè, không ẩn dữ liệu gốc.
4. Bấm lại "Hiệu chỉnh" → **phát hiện Bug #3** → sửa → form giờ pre-fill đúng.
5. Sửa lại nội dung + lý do mới → Lưu → `version` tăng lên 2, DB có 2 audit event (CREATED, UPDATED) với đúng before/after.
6. Bấm "Xóa hiệu chỉnh" → toast "Đã xóa hiệu chỉnh" → DB xác nhận: 0 override còn lại, 3 audit event tổng (CREATED/UPDATED/DELETED), **10 resolution tự động hoàn toàn không đổi**.
7. Test RBAC qua API thật (không chỉ ẩn nút UI): `LECTURER` gọi `GET /needs-review` → **403 FORBIDDEN** thật; `LECTURER` gọi `GET /publications/{eid}` → đọc được, thấy đúng override (public-safe, không lộ UUID) — xác nhận "quyền đọc học thuật tách khỏi quyền sửa" đúng như yêu cầu.
8. Trong lúc dựng môi trường test cho bước này, phát hiện và sửa luôn **Bug #1, #2** nêu trên nhờ chính việc thao tác UI thật chứ không chỉ dựa vào test tự động.

### Chưa kiểm thử được qua UI (ghi nhận trung thực)
- **Hai ADMIN sửa cùng lúc qua 2 trình duyệt riêng** (thao tác tay thật) chưa làm — đã kiểm thử tương đương bằng test tích hợp gọi 2 session DB thật đồng thời (xác nhận đúng 1 ghi thành công, 1 bị từ chối), nhưng chưa quan sát trực quan qua 2 cửa sổ trình duyệt song song.
- **Dữ liệu mâu thuẫn thật giữa nhiều nguồn** (`CONFLICTING_SOURCES`) chưa có ví dụ thật trong bộ dữ liệu 3 DOI hiện có (cả 3 DOI test chỉ sinh ra UNRESOLVED/LOW_CONFIDENCE, không có trường hợp 1 nguồn VERIFIED + 1 nguồn khác mâu thuẫn) — logic phân loại `CONFLICTING_SOURCES` đã viết và có test riêng dùng dữ liệu tổng hợp, nhưng chưa quan sát qua UI với dữ liệu online thật.

## 4. KIỂM TRA CHUNG (Phần VII)

| Hạng mục | Kết quả |
|---|---|
| Backend tests | **927 passed, 5 skipped, 0 failed** (907 trước đó + 20 mới) |
| Frontend typecheck + build | PASS, 0 lỗi |
| Alembic | 1 head duy nhất: `b5e8d2f1a4c7` (trên DB test). **App DB xác nhận lại lần cuối: vẫn `f6a1b2c3d4e5`, 660 publications — chưa migrate, chưa chạm.** |
| RBAC | Xác nhận qua API thật (không chỉ UI): LECTURER/REVIEWER 403 trên toàn bộ endpoint rà soát/hiệu chỉnh |
| Provenance/audit | 3 audit event đầy đủ before/after cho 1 vòng đời override (tạo → sửa → xóa) |
| App DB / teacher DB | Không bị động tới trong toàn bộ phiên |
| `/system/reset` | Không chạm |

## 5. GATE 2 — KẾT LUẬN

**PASS** cho phạm vi đã kiểm thử: ADMIN xử lý được trọn vẹn trường hợp máy không xác định được đơn vị (UNRESOLVED) qua giao diện thật, có bằng chứng (URL + lý do bắt buộc), có audit trước/sau đầy đủ, và không phá dữ liệu nguồn (Scopus raw, resolution tự động đều nguyên vẹn qua toàn bộ thao tác tạo/sửa/xóa/chạy lại thu thập).

**Đáng chú ý:** 2 trong 3 bug thật tìm thấy (rò rỉ ID nội bộ, crash khi đã có override) **không bị bất kỳ test tự động nào ban đầu bắt được** — chỉ lộ ra khi thao tác qua trình duyệt thật theo đúng trình tự ADMIN sẽ dùng (tạo override → mở lại rà soát). Cả 2 đã được sửa và có test hồi quy riêng.

**Chưa kiểm thử đầy đủ** (ghi nhận, không chặn Gate 2): 2 ADMIN qua 2 cửa sổ trình duyệt thật song song; dữ liệu `CONFLICTING_SOURCES` thật từ nguồn online (hiện chỉ có dữ liệu tổng hợp).

**Chuyển sang Ưu tiên 3**, chờ bạn xem báo cáo này trước.
