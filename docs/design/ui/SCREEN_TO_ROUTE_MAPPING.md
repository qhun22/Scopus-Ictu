# Screen-to-Route Mapping — Scopus–ICTU · Task 20B

**Nguồn:** `frontend/src/App.tsx` (commit 530bf0f) + chỉnh sửa Task 20A/R2

---

## Bảng ánh xạ đầy đủ

| Screen ID | Tên màn | Route | Method | Role được phép | Component React | File | Ghi chú |
|---|---|---|---|---|---|---|---|
| S01 | Đăng nhập | /login | GET | PUBLIC | Login | pages/Login/index.tsx | Redirect → /home nếu đã đăng nhập |
| S19 | Trang chủ | /home | GET | ADMIN, REVIEWER, LECTURER | Home | pages/Home/index.tsx | Redirect mặc định sau đăng nhập |
| S05 | Tổng quan | /dashboard | GET | ADMIN | Dashboard | pages/Dashboard/index.tsx | REVIEWER → redirect /home |
| S04 | Nhập dữ liệu | /imports | GET | ADMIN | Imports | pages/Imports/index.tsx | — |
| S21 | Chuẩn hóa | /normalization | GET | ADMIN | Normalization | pages/Normalization/index.tsx | — |
| S06 | Danh sách giảng viên | /lecturers | GET | ADMIN | Lecturers | pages/Lecturers/index.tsx | — |
| S02 | Danh sách công bố | /publications | GET | ADMIN, REVIEWER | Publications | pages/Publications/index.tsx | — |
| S03 | Chi tiết công bố | /publications/:eid | GET | ADMIN, REVIEWER | PublicationDetail | pages/Publications/Detail.tsx | — |
| S09 | Hàng đợi duyệt | /reviews | GET | ADMIN, REVIEWER | ApprovalQueue | pages/ApprovalQueue/index.tsx | — |
| S13 | Lịch sử review | /review-history | GET | ADMIN, REVIEWER | ReviewHistory | pages/ReviewHistory/index.tsx | — |
| S14 | Nhật ký hệ thống | /audit-logs | GET | ADMIN | AuditLogs | pages/AuditLogs/index.tsx | — |
| S15 | Tác vụ | /tasks | GET | ADMIN | Tasks (placeholder) | pages/Tasks/ (PlaceholderPage) | "Chức năng đang phát triển" |
| S16 | Hồ sơ cá nhân | /profile | GET | LECTURER | LecturerProfile | pages/Lecturer/Profile.tsx | — |
| S17 | Liên kết Scopus | /identity | GET | LECTURER | LecturerIdentity | pages/Lecturer/Identity.tsx | — |
| S18 | Công bố của tôi | /my-publications | GET | LECTURER | MyPublications | pages/Lecturer/MyPublications.tsx | — |
| S20 | So sánh chuẩn hóa | /publications/:eid/normalization | GET | ADMIN | (CHƯA TỒN TẠI) | — | PROPOSED; API chưa có |

---

## RBAC — Ma trận phân quyền (theo App.tsx)

| Route | ADMIN | REVIEWER | LECTURER | PUBLIC |
|---|---|---|---|---|
| /login | redirect/home | redirect/home | redirect/home | ✅ |
| /home | ✅ | ✅ | ✅ | redirect/login |
| /dashboard | ✅ | ❌ redirect/home | ❌ redirect/home | redirect/login |
| /imports | ✅ | ❌ | ❌ | redirect/login |
| /normalization | ✅ | ❌ | ❌ | redirect/login |
| /lecturers | ✅ | ❌ | ❌ | redirect/login |
| /publications | ✅ | ✅ | ❌ | redirect/login |
| /publications/:eid | ✅ | ✅ | ❌ | redirect/login |
| /reviews | ✅ | ✅ | ❌ | redirect/login |
| /review-history | ✅ | ✅ | ❌ | redirect/login |
| /audit-logs | ✅ | ❌ | ❌ | redirect/login |
| /tasks | ✅ | ❌ | ❌ | redirect/login |
| /profile | ❌ | ❌ | ✅ | redirect/login |
| /identity | ❌ | ❌ | ✅ | redirect/login |
| /my-publications | ❌ | ❌ | ✅ | redirect/login |

> Đã xác minh bằng ảnh chụp:  
> - R_blocked_dashboard: REVIEWER → /dashboard → chuyển /home ✅  
> - L_blocked_reviews: LECTURER → /reviews → chuyển /home ✅

---

## Menu sidebar theo vai trò (Sidebar.tsx)

### ADMIN (10 mục)
1. Trang chủ → /home
2. Tổng quan → /dashboard
3. Nhập dữ liệu → /imports
4. Chuẩn hóa dữ liệu → /normalization
5. Giảng viên → /lecturers
6. Công bố → /publications
7. Duyệt đối sánh → /reviews
8. Lịch sử review → /review-history
9. Nhật ký hệ thống → /audit-logs
10. Tác vụ → /tasks

### REVIEWER (4 mục)
1. Trang chủ → /home
2. Công bố → /publications
3. Duyệt đối sánh → /reviews
4. Lịch sử review → /review-history

### LECTURER (4 mục)
1. Trang chủ → /home
2. Hồ sơ cá nhân → /profile
3. Công bố của tôi → /my-publications
4. Liên kết Scopus → /identity

---

## Figma Page mapping

| Figma Page | Section | Screen IDs |
|---|---|---|
| Page 1 "00–02 · Cover · Design Foundations · Components" | 00 — Cover | — |
| Page 1 "00–02 · Cover · Design Foundations · Components" | 01 — Design Foundations | Swatches màu, mẫu chữ, spacing |
| Page 1 "00–02 · Cover · Design Foundations · Components" | 02 — Components | (chờ hoàn thiện) |
| Page 2 "03–06 · Screens · User Flows & Prototype" | 03 — Core Screens | S01/S05/S04/S06/S02/S03/S19/S21 |
| Page 2 "03–06 · Screens · User Flows & Prototype" | 04 — Review & Governance | S09–S14/S15 |
| Page 2 "03–06 · Screens · User Flows & Prototype" | 05 — Proposed Screens | S20 |
| Page 2 "03–06 · Screens · User Flows & Prototype" | 06 — User Flows & Prototype | Flow 1–6 |
| Page 3 "07 · Design Handoff + 99 LEGACY v0" | 07 — Design Handoff | Bảng handoff |
| Page 3 "07 · Design Handoff + 99 LEGACY v0" | 99 — LEGACY v0 | FG-01…FG-17 (9 frame cũ) |
