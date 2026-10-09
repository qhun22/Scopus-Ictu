"""Task 10: pure author-affiliation alignment (synthetic data only)."""

from __future__ import annotations

from app.services.author_affiliation import (
    CORROBORATED,
    UNRESOLVED,
    VERIFIED,
    ExternalAuthorship,
    ScopusAuthorSlot,
    align_paper,
    name_tokens,
    names_match,
    parse_crossref_authors,
    parse_openalex_authorships,
    parse_orcid_scopus_ids,
    parse_scopus_author_slots,
)


def slots(*names):
    return [ScopusAuthorSlot(str(1000000000 + i), i, n) for i, n in enumerate(names, start=1)]


def ext(pos, name, orcid=None, raw=(), source="openalex"):
    return ExternalAuthorship(source, pos, name, orcid, tuple(raw))


def test_name_tokens_ignore_order_accents_hyphens_and_scopus_id_suffix() -> None:
    assert names_match("Nguyen, Thanh-Tung (58035626100)", "Thanh-Tung Nguyen")
    assert names_match("Đặng, Văn Hùng", "Van-Hung Dang")
    assert not names_match("Nguyen, T.", "Thanh-Tung Nguyen")  # initials are not enough
    assert not names_match("", "")
    assert name_tokens("Le, Hung Linh") == ("hung", "le", "linh")


def test_scopus_slots_pair_names_by_id_not_by_position() -> None:
    result = parse_scopus_author_slots(
        "111111; 222222", "Beta, Bob (222222); Alpha, Ann (111111)"
    )
    assert [(s.scopus_id, s.author_order, s.full_name) for s in result] == [
        ("111111", 1, "Alpha, Ann"),
        ("222222", 2, "Beta, Bob"),
    ]


def test_verified_by_orcid_chain_even_when_names_differ() -> None:
    s = slots("Alpha, Ann", "Beta, Bob")
    externals = [ext(1, "A. Alpha", "0000-0001-0000-0001", ["Dept X, Univ Y"]), ext(2, "Bob Beta")]
    links = align_paper(s, externals, {"0000-0001-0000-0001": {s[0].scopus_id}}, source="openalex")
    assert links[0].status == VERIFIED and links[0].evidence.startswith("ORCID:")
    assert links[0].raw_affiliations == ("Dept X, Univ Y",)
    assert links[1].status == CORROBORATED  # position + count + name


def test_orcid_pointing_to_scopus_id_not_on_this_paper_gives_no_proof() -> None:
    s = slots("Alpha, Ann")
    links = align_paper(s, [ext(1, "Someone Else", "0000-0001-0000-0002")], {"0000-0001-0000-0002": {"999999999"}}, source="openalex")
    assert links[0].status == UNRESOLVED and links[0].reason == "NAME_MISMATCH"
    assert links[0].raw_affiliations == ()  # nothing assigned when unresolved


def test_count_mismatch_is_unresolved_without_id_evidence() -> None:
    s = slots("Alpha, Ann", "Beta, Bob")
    links = align_paper(s, [ext(1, "Ann Alpha", raw=["Univ"])], {}, source="openalex")
    assert {l.status for l in links} == {UNRESOLVED} and {l.reason for l in links} == {"AUTHOR_COUNT_MISMATCH"}
    assert all(l.raw_affiliations == () for l in links)


def test_count_mismatch_still_allows_id_verified_slot() -> None:
    s = slots("Alpha, Ann", "Beta, Bob", "Gamma, Gus")
    externals = [ext(1, "Ann Alpha", "0000-0001-0000-0003", ["Univ A"]), ext(2, "Bob Beta")]
    links = align_paper(s, externals, {"0000-0001-0000-0003": {s[0].scopus_id}}, source="openalex")
    assert [l.status for l in links] == [VERIFIED, UNRESOLVED, UNRESOLVED]


def test_name_mismatch_at_same_position_is_unresolved() -> None:
    s = slots("Alpha, Ann")
    link = align_paper(s, [ext(1, "Zed Zeta", raw=["Univ"])], {}, source="crossref")[0]
    assert link.status == UNRESOLVED and link.reason == "NAME_MISMATCH" and link.raw_affiliations == ()


def test_verified_id_contradicting_order_invalidates_positional_claims() -> None:
    s = slots("Alpha, Ann", "Beta, Bob")
    # ORCID says slot 2 (Bob) is the external author at position 1 -> list order is not trustworthy
    externals = [ext(1, "Bob Beta", "0000-0001-0000-0004", ["Univ B"]), ext(2, "Ann Alpha", raw=["Univ A"])]
    links = align_paper(s, externals, {"0000-0001-0000-0004": {s[1].scopus_id}}, source="openalex")
    assert links[1].status == VERIFIED and links[1].external_position == 1
    assert links[0].status == UNRESOLVED and links[0].reason == "POSITION_CLAIMED_BY_OTHER_ID"


def test_two_externals_claiming_same_scopus_id_is_a_conflict() -> None:
    s = slots("Alpha, Ann", "Beta, Bob")
    bridge = {"0000-0001-0000-0005": {s[0].scopus_id}, "0000-0001-0000-0006": {s[0].scopus_id}}
    externals = [ext(1, "Ann Alpha", "0000-0001-0000-0005"), ext(2, "Ann Alpha", "0000-0001-0000-0006")]
    links = align_paper(s, externals, bridge, source="openalex")
    assert links[0].status == UNRESOLVED and links[0].reason == "ID_CONFLICT"


def test_multiple_affiliations_and_organizations_are_preserved_separately() -> None:
    work = {
        "authorships": [
            {
                "author": {"display_name": "Ann Alpha", "orcid": "https://orcid.org/0000-0001-0000-0007"},
                "raw_affiliation_strings": ["Faculty of A, University X", "Institute B, Country Z"],
                "institutions": [
                    {"id": "https://openalex.org/I1", "display_name": "University X", "ror": "https://ror.org/aaa", "country_code": "VN"},
                    {"id": "https://openalex.org/I2", "display_name": "Institute B", "ror": None, "country_code": "ZZ"},
                ],
            },
            {"author": {"display_name": "Bob Beta"}, "raw_affiliation_strings": [], "institutions": []},
        ]
    }
    parsed = parse_openalex_authorships(work)
    assert parsed[0].orcid == "0000-0001-0000-0007" and len(parsed[0].raw_affiliations) == 2
    assert [o.source_org_id for o in parsed[0].organizations] == ["https://openalex.org/I1", "https://openalex.org/I2"]
    s = slots("Alpha, Ann", "Beta, Bob")
    links = align_paper(s, parsed, {"0000-0001-0000-0007": {s[0].scopus_id}}, source="openalex")
    assert links[0].has_affiliation and len(links[0].organizations) == 2
    # Bob is corroborated but the source has NO affiliation: nothing is invented
    assert links[1].status == CORROBORATED and not links[1].has_affiliation


def test_crossref_parser_and_orcid_scopus_extraction() -> None:
    parsed = parse_crossref_authors(
        {"author": [{"given": "Ann", "family": "Alpha", "ORCID": "http://orcid.org/0000-0001-0000-0008", "affiliation": [{"name": "Univ X"}]},
                    {"name": "Consortium"}]}
    )
    assert parsed[0].orcid == "0000-0001-0000-0008" and parsed[0].raw_affiliations == ("Univ X",)
    assert parsed[1].display_name == "Consortium"
    ids = parse_orcid_scopus_ids(
        [
            {"type": "Scopus Author ID", "value": "57218489216", "url": None},
            {"type": "ResearcherID", "value": "A-1234-2020", "url": None},
            {"type": "Scopus Author ID", "value": None, "url": "http://www.scopus.com/inward/authorDetails.url?authorID=56719215900&partnerID=x"},
        ]
    )
    assert ids == frozenset({"57218489216", "56719215900"})
