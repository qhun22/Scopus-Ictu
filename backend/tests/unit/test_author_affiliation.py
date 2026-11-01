"""Task 10: pure author-affiliation alignment (synthetic data only)."""

from __future__ import annotations

import pytest

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


def ext(pos, name, orcid=None, raw=(), source="crossref"):
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
    links = align_paper(s, externals, {"0000-0001-0000-0001": {s[0].scopus_id}}, source="crossref")
    assert links[0].status == VERIFIED and links[0].evidence.startswith("ORCID:")
    assert links[0].raw_affiliations == ("Dept X, Univ Y",)
    assert links[1].status == CORROBORATED  # position + count + name


def test_orcid_pointing_to_scopus_id_not_on_this_paper_gives_no_proof() -> None:
    s = slots("Alpha, Ann")
    links = align_paper(
        s, [ext(1, "Someone Else", "0000-0001-0000-0002")],
        {"0000-0001-0000-0002": {"999999999"}}, source="crossref",
    )
    assert links[0].status == UNRESOLVED and links[0].reason == "NAME_MISMATCH"
    assert links[0].raw_affiliations == ()  # nothing assigned when unresolved


def test_count_mismatch_is_unresolved_without_id_evidence() -> None:
    s = slots("Alpha, Ann", "Beta, Bob")
    links = align_paper(s, [ext(1, "Ann Alpha", raw=["Univ"])], {}, source="crossref")
    assert {l.status for l in links} == {UNRESOLVED} and {l.reason for l in links} == {"AUTHOR_COUNT_MISMATCH"}
    assert all(l.raw_affiliations == () for l in links)


def test_count_mismatch_still_allows_id_verified_slot() -> None:
    s = slots("Alpha, Ann", "Beta, Bob", "Gamma, Gus")
    externals = [ext(1, "Ann Alpha", "0000-0001-0000-0003", ["Univ A"]), ext(2, "Bob Beta")]
    links = align_paper(s, externals, {"0000-0001-0000-0003": {s[0].scopus_id}}, source="crossref")
    assert [l.status for l in links] == [VERIFIED, UNRESOLVED, UNRESOLVED]


def test_name_mismatch_at_same_position_is_unresolved() -> None:
    s = slots("Alpha, Ann")
    link = align_paper(s, [ext(1, "Zed Zeta", raw=["Univ"])], {}, source="crossref")[0]
    assert link.status == UNRESOLVED and link.reason == "NAME_MISMATCH" and link.raw_affiliations == ()


def test_verified_id_contradicting_order_invalidates_positional_claims() -> None:
    s = slots("Alpha, Ann", "Beta, Bob")
    # ORCID says slot 2 (Bob) is the external author at position 1 -> list order is not trustworthy
    externals = [ext(1, "Bob Beta", "0000-0001-0000-0004", ["Univ B"]), ext(2, "Ann Alpha", raw=["Univ A"])]
    links = align_paper(s, externals, {"0000-0001-0000-0004": {s[1].scopus_id}}, source="crossref")
    assert links[1].status == VERIFIED and links[1].external_position == 1
    assert links[0].status == UNRESOLVED and links[0].reason == "POSITION_CLAIMED_BY_OTHER_ID"


def test_two_externals_claiming_same_scopus_id_is_a_conflict() -> None:
    s = slots("Alpha, Ann", "Beta, Bob")
    bridge = {"0000-0001-0000-0005": {s[0].scopus_id}, "0000-0001-0000-0006": {s[0].scopus_id}}
    externals = [ext(1, "Ann Alpha", "0000-0001-0000-0005"), ext(2, "Ann Alpha", "0000-0001-0000-0006")]
    links = align_paper(s, externals, bridge, source="crossref")
    assert links[0].status == UNRESOLVED and links[0].reason == "ID_CONFLICT"


def test_multiple_affiliations_and_organizations_are_preserved_separately() -> None:
    work = {
        "authorships": [
            {
                "raw_author_name": "Ann Alpha",
                "author": {"display_name": "Ann Alpha", "orcid": "https://orcid.org/0000-0001-0000-0007"},
                "raw_affiliation_strings": ["Faculty of A, University X", "Institute B, Country Z"],
                "institutions": [
                    {"id": "https://openalex.org/I1", "display_name": "University X", "ror": "https://ror.org/aaa", "country_code": "VN"},
                    {"id": "https://openalex.org/I2", "display_name": "Institute B", "ror": None, "country_code": "ZZ"},
                ],
            },
            {"raw_author_name": "Bob Beta", "author": {"display_name": "Bob Beta"},
             "raw_affiliation_strings": [], "institutions": []},
        ]
    }
    parsed = parse_openalex_authorships(work)
    assert parsed[0].orcid is None and len(parsed[0].raw_affiliations) == 2
    assert parsed[0].entity_orcid == "https://orcid.org/0000-0001-0000-0007"
    assert [o.source_org_id for o in parsed[0].organizations] == ["https://openalex.org/I1", "https://openalex.org/I2"]
    s = slots("Alpha, Ann", "Beta, Bob")
    links = align_paper(s, parsed, {"0000-0001-0000-0007": {s[0].scopus_id}}, source="openalex")
    assert links[0].status == CORROBORATED
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


def test_openalex_entries_keep_the_sources_own_raw_to_organization_pairing() -> None:
    work = {
        "authorships": [
            {
                "author": {"display_name": "Ann Alpha"},
                "raw_affiliation_strings": ["Dept A, University X, Country", "Unknown Lab"],
                "affiliations": [
                    {"raw_affiliation_string": "Dept A, University X, Country", "institution_ids": ["I1", "I2"]},
                    {"raw_affiliation_string": "Unknown Lab", "institution_ids": []},
                ],
                "institutions": [
                    {"id": "I1", "display_name": "University X", "ror": "r1", "country_code": "VN"},
                    {"id": "I2", "display_name": "Consortium Y", "ror": None, "country_code": None},
                ],
            }
        ]
    }
    entries = parse_openalex_authorships(work)[0].entries
    assert [e.raw_text for e in entries] == ["Dept A, University X, Country", "Unknown Lab"]
    assert [o.source_org_id for o in entries[0].organizations] == ["I1", "I2"]
    assert entries[1].organizations == ()  # not normalized by the source -> stays unnormalized


def test_openalex_entries_without_pairing_do_not_invent_it() -> None:
    work = {
        "authorships": [
            {
                "author": {"display_name": "Ann Alpha"},
                "raw_affiliation_strings": ["Somewhere"],
                "institutions": [{"id": "I9", "display_name": "Org Nine"}],
            }
        ]
    }
    entries = parse_openalex_authorships(work)[0].entries
    assert [(e.raw_text, [o.source_org_id for o in e.organizations]) for e in entries] == [("Somewhere", []), (None, ["I9"])]


class TestOpenAlexTrustBoundary:
    ORCID = "0000-0001-0000-0042"

    @classmethod
    def authorship(cls, raw_name="Ann Alpha", entity_name="Ann Alpha", *, affiliations=()):
        return {
            "raw_author_name": raw_name,
            "author": {
                "id": "https://openalex.org/A-SYNTHETIC",
                "display_name": entity_name,
                "orcid": "https://orcid.org/" + cls.ORCID,
            },
            "raw_affiliation_strings": list(affiliations),
        }

    def test_entity_conflict_keeps_raw_name_and_never_verifies_slot(self):
        s = slots("Alpha, Ann")
        work = {"authorships": [self.authorship(
            entity_name="Bert Birch", affiliations=["Synthetic Faculty"]
        )]}
        parsed = parse_openalex_authorships(work)
        link = align_paper(s, parsed, {self.ORCID: {s[0].scopus_id}}, source="openalex")[0]

        assert parsed[0].display_name == parsed[0].raw_author_name == "Ann Alpha"
        assert parsed[0].orcid is None
        assert parsed[0].entity_id == "https://openalex.org/A-SYNTHETIC"
        assert parsed[0].entity_display_name == "Bert Birch"
        assert parsed[0].entity_orcid == "https://orcid.org/" + self.ORCID
        assert link.status == UNRESOLVED
        assert link.reason == "OPENALEX_ENTITY_NAME_CONFLICT"
        assert link.raw_affiliations == () and not link.has_affiliation
        assert link.observation["raw_author_name"] == "Ann Alpha"
        assert link.observation["raw_affiliations"] == ["Synthetic Faculty"]
        assert link.observation["openalex_author_entity"]["display_name"] == "Bert Birch"

    def test_same_entity_name_does_not_make_entity_orcid_independent_proof(self):
        s = slots("Alpha, Ann", "Birch, Bert")
        work = {"authorships": [self.authorship(), self.authorship("Bert Birch", "Bert Birch")]}
        parsed = parse_openalex_authorships(work)
        links = align_paper(s, parsed, {self.ORCID: {s[1].scopus_id}}, source="openalex")

        assert [link.status for link in links] == [CORROBORATED, CORROBORATED]
        assert all(link.evidence == "POSITION+COUNT+NAME" for link in links)
        assert all(author.orcid is None for author in parsed)

    @pytest.mark.parametrize("context_source", ["openalex", "crossref"])
    def test_direct_openalex_authorship_cannot_bypass_parser_trust_boundary(self, context_source):
        s = slots("Alpha, Ann")
        legacy = ExternalAuthorship("openalex", 1, "A. Alpha", self.ORCID)
        link = align_paper(s, [legacy], {self.ORCID: {s[0].scopus_id}},
                           source=context_source)[0]
        assert link.status != VERIFIED
        assert not link.evidence or not link.evidence.startswith("ORCID:")

    def test_publisher_identifier_keeps_valid_support_despite_name_variant(self):
        s = slots("Alpha, Ann")
        parsed = parse_crossref_authors({"author": [{
            "given": "A.", "family": "Alpha", "ORCID": "https://orcid.org/" + self.ORCID,
            "affiliation": [{"name": "Publisher Faculty"}],
        }]})
        link = align_paper(s, parsed, {self.ORCID: {s[0].scopus_id}}, source="crossref")[0]

        assert link.status == VERIFIED
        assert link.raw_affiliations == ("Publisher Faculty",)
        assert link.observation["publisher_orcid"] == self.ORCID
        assert link.observation["source_tier"] == "PUBLISHER"

    def test_publisher_orcid_without_registry_bridge_is_not_verified(self):
        s = slots("Alpha, Ann")
        parsed = parse_crossref_authors({"author": [{
            "given": "Ann", "family": "Alpha", "ORCID": "https://orcid.org/" + self.ORCID,
        }]})
        link = align_paper(s, parsed, {}, source="crossref")[0]
        assert link.status == CORROBORATED
        assert link.observation["publisher_orcid"] == self.ORCID

    def test_same_name_coauthors_and_initials_do_not_gain_entity_verification(self):
        s = slots("Alpha, Ann", "Alpha, Ann", "Birch, Bert")
        work = {"authorships": [
            self.authorship(), self.authorship(), self.authorship("B. Birch", "B. Birch")
        ]}
        links = align_paper(s, parse_openalex_authorships(work),
                            {self.ORCID: {s[1].scopus_id}}, source="openalex")
        assert [link.status for link in links] == [CORROBORATED, CORROBORATED, UNRESOLVED]
        assert links[2].reason == "NAME_MISMATCH"
        assert [link.external_position for link in links] == [1, 2, 3]

    @pytest.mark.parametrize("missing", ["orcid", "display_name", "author"])
    def test_missing_entity_fields_do_not_replace_raw_authorship(self, missing):
        row = self.authorship(affiliations=["Raw Faculty"])
        if missing == "author":
            row.pop("author")
        else:
            row["author"].pop(missing)
        link = align_paper(slots("Alpha, Ann"), parse_openalex_authorships({"authorships": [row]}),
                           {}, source="openalex")[0]
        assert link.status == CORROBORATED
        assert link.external_name == "Ann Alpha" and link.raw_affiliations == ("Raw Faculty",)

    def test_missing_raw_name_is_insufficient_even_with_matching_entity(self):
        s = slots("Alpha, Ann")
        row = self.authorship(affiliations=["Raw Faculty"])
        row.pop("raw_author_name")
        link = align_paper(s, parse_openalex_authorships({"authorships": [row]}),
                           {self.ORCID: {s[0].scopus_id}}, source="openalex")[0]
        assert link.status == UNRESOLVED and link.reason == "NO_RAW_AUTHOR_NAME"
        assert link.observation["raw_author_name"] is None
        assert link.observation["raw_affiliations"] == ["Raw Faculty"]
        assert link.observation["openalex_author_entity"]["display_name"] == "Ann Alpha"

    def test_multiple_raw_affiliations_and_missing_affiliation_remain_distinct(self):
        work = {"authorships": [self.authorship(affiliations=["Faculty A", "Institute B"])]}
        s = slots("Alpha, Ann")
        link = align_paper(s, parse_openalex_authorships(work), {}, source="openalex")[0]
        assert link.status == CORROBORATED
        assert link.raw_affiliations == ("Faculty A", "Institute B")
        assert [entry.raw_text for entry in link.entries] == ["Faculty A", "Institute B"]
        assert link.has_affiliation

        work["authorships"][0]["raw_affiliation_strings"] = []
        empty = align_paper(s, parse_openalex_authorships(work), {}, source="openalex")[0]
        assert empty.status == CORROBORATED and not empty.has_affiliation

    def test_seventh_author_retains_target_slot_and_raw_provenance(self):
        names = [f"Synthetic Person{i}" for i in range(1, 8)]
        s = slots(*names)
        work = {"authorships": [self.authorship(name, name) for name in names]}
        links = align_paper(s, parse_openalex_authorships(work),
                            {self.ORCID: {s[0].scopus_id}}, source="openalex")
        assert len(links) == 7 and all(link.status == CORROBORATED for link in links)
        assert links[6].external_position == links[6].author_order == 7
        assert links[6].scopus_id == s[6].scopus_id
        assert links[6].observation["raw_author_name"] == names[6]

    def test_missing_author_list_is_not_entity_conflict(self):
        link = align_paper(slots("Alpha, Ann"), parse_openalex_authorships({}),
                           {}, source="openalex")[0]
        assert link.status == UNRESOLVED and link.reason == "NO_EXTERNAL_AUTHOR_LIST"
