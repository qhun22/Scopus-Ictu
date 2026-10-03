"""Unit tests for the DSpace archive HTML parser (M2.5A §50).

These tests run fully offline against synthetic HTML fragments that
mirror the schema.org ``Person`` markup produced by the ICTU DSpace
WordPress theme (``<article class="gv-card dl-card">`` blocks).
"""

from __future__ import annotations

from html import escape as _html_escape

from app.services.lecturer_dataset.dspace_parser import (
    ExtractedRecord,
    extract_records,
    normalise_records,
)


def _wrap_card(
    *,
    full_name: str,
    url: str,
    job_title: str | None = None,
    honorific_prefix: str | None = None,
    knows_about: str | None = None,
    email: str | None = None,
    data_rank: str = "ts",
    data_degree: str = "ts",
    data_position: str = "",
) -> str:
    """Build a single ``<article class="gv-card dl-card">`` fragment."""
    meta_items: list[str] = []
    if job_title:
        meta_items.append(
            f'<li><span itemprop="jobTitle">{_html_escape(job_title)}</span></li>'
        )
    if honorific_prefix:
        meta_items.append(
            f'<li><span itemprop="honorificPrefix">{_html_escape(honorific_prefix)}</span></li>'
        )
    if knows_about:
        meta_items.append(
            f'<li><span itemprop="knowsAbout">{_html_escape(knows_about)}</span></li>'
        )
    if email:
        meta_items.append(
            f'<li><a href="mailto:{email}" itemprop="email">{email}</a></li>'
        )
    meta_html = "\n".join(meta_items)
    return (
        f'<article class="gv-card dl-card" itemscope itemtype="https://schema.org/Person" '
        f'data-rank="{data_rank}" data-degree="{data_degree}" data-position="{_html_escape(data_position)}">\n'
        f'  <h2 class="gv-name" itemprop="name">\n'
        f'    <a href="{url}" itemprop="url">{_html_escape(full_name)}</a>\n'
        f'  </h2>\n'
        f'  <ul>{meta_html}</ul>\n'
        f'</article>\n'
    )


def test_extract_records_parses_basic_pgs_ts_card() -> None:
    html = _wrap_card(
        full_name="PGS.TS. Phùng Trung Nghĩa",
        url="https://repository.ictu.edu.vn/giang-vien/phung-trung-nghia/",
        job_title="Hiệu trưởng",
        honorific_prefix="PGS – TS",
        knows_about="CNTT",
        email="ptnghia@ictu.edu.vn",
        data_rank="pgs",
        data_degree="ts",
        data_position="hiệu trưởng",
    )
    recs = extract_records(html)
    assert len(recs) == 1
    rec = recs[0]
    assert rec.full_name == "PGS.TS. Phùng Trung Nghĩa"
    assert rec.academic_degree == "TS"
    assert rec.academic_rank == "PGS"
    assert rec.position == "hiệu trưởng"
    assert rec.known_specialisation == "CNTT"
    assert rec.institutional_email == "ptnghia@ictu.edu.vn"
    assert rec.profile_url == "https://repository.ictu.edu.vn/giang-vien/phung-trung-nghia/"


def test_extract_records_handles_missing_honorific_prefix() -> None:
    """Cards without an honorific prefix fall back to ``data-rank`` /
    ``data-degree`` attributes (defensive fallback)."""
    html = _wrap_card(
        full_name="Đoàn Mạn Cường",
        url="https://repository.ictu.edu.vn/giang-vien/doan-man-cuong/",
        data_rank="",
        data_degree="",
    )
    recs = extract_records(html)
    assert len(recs) == 1
    assert recs[0].academic_degree is None
    assert recs[0].academic_rank is None


def test_extract_records_dedupes_by_name_and_url() -> None:
    """Two cards with the same full_name + profile_url collapse to one."""
    html = _wrap_card(
        full_name="Trùng Tên",
        url="https://repository.ictu.edu.vn/giang-vien/trung-ten/",
        data_rank="",
        data_degree="",
    ) + _wrap_card(
        full_name="Trùng Tên",
        url="https://repository.ictu.edu.vn/giang-vien/trung-ten/",
        data_rank="",
        data_degree="",
    )
    recs = normalise_records(extract_records(html))
    assert len(recs) == 1
    assert recs[0]["full_name"] == "Trùng Tên"


def test_extract_records_keeps_distinct_cards_with_same_name() -> None:
    """Two cards with the same name but different profile URLs MUST
    remain separate (M2.5A §17: identity is not determined by name)."""
    html = _wrap_card(
        full_name="Nguyễn Văn A",
        url="https://repository.ictu.edu.vn/giang-vien/nguyen-van-a/",
        data_rank="",
        data_degree="",
    ) + _wrap_card(
        full_name="Nguyễn Văn A",
        url="https://repository.ictu.edu.vn/giang-vien/nguyen-van-a-2/",
        data_rank="",
        data_degree="",
    )
    recs = normalise_records(extract_records(html))
    assert len(recs) == 2
    urls = sorted(r["profile_url"] for r in recs)
    assert urls == sorted(
        [
            "https://repository.ictu.edu.vn/giang-vien/nguyen-van-a/",
            "https://repository.ictu.edu.vn/giang-vien/nguyen-van-a-2/",
        ]
    )


def test_extract_records_preserves_unicode_vietnamese() -> None:
    html = _wrap_card(
        full_name="Nguyễn Thị Hải Anh",
        url="https://repository.ictu.edu.vn/giang-vien/nguyen-thi-hai-anh/",
        knows_about="Khoa học máy tính",
        email="nthainh@ictu.edu.vn",
        data_rank="",
        data_degree="ths",
    )
    recs = extract_records(html)
    assert len(recs) == 1
    assert recs[0].full_name == "Nguyễn Thị Hải Anh"
    assert recs[0].known_specialisation == "Khoa học máy tính"


def test_extract_records_returns_empty_for_empty_html() -> None:
    assert extract_records("") == []
    assert extract_records("<html><body>no cards</body></html>") == []
