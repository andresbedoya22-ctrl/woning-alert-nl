from dataclasses import replace
from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.parsers import ParsedListing, ParserFamilyResult, ParserInput, parse_realworks_listing_page
from domek_wonen.qa import qa_parser_family_result


def _parser_input(html: str, *, domain: str = "example.nl", url: str | None = None) -> ParserInput:
    return ParserInput(
        source_id=f"{domain}__test",
        source_domain=domain,
        source_url=url or f"https://www.{domain}/aanbod/woningaanbod/koop",
        content=html,
        content_type="html",
    )


def _qa_listing(**overrides: object) -> ParsedListing:
    listing = ParsedListing(
        source_id="example.nl__test",
        source_domain="example.nl",
        canonical_url="https://www.example.nl/aanbod/woningaanbod/breda/koop/huis-1001-zonnelaan-12",
        address_raw="Zonnelaan 12",
        street="Zonnelaan",
        house_number="12",
        city="Breda",
        asking_price_eur=425000,
        transaction_type="koop",
        status="beschikbaar",
        property_type="house",
        confidence_score=0.90,
        needs_review=False,
    )
    return replace(listing, **overrides)


def _result(listing: ParsedListing) -> ParserFamilyResult:
    return ParserFamilyResult(
        parser_family="realworks_public",
        source_id=listing.source_id,
        source_domain=listing.source_domain,
        listings=(listing,),
    )


def test_parses_realworks_listing_card_and_qa_clean() -> None:
    html = """
    <ul>
      <li class="al4woning aanbodEntry even" data-paginatable="true">
        <a class="aanbodEntryLink" href="/aanbod/woningaanbod/breda/koop/huis-1001-zonnelaan-12/">
          <img alt="Zonnelaan 12 in Breda" />
        </a>
        <a class="aanbodEntryLink" href="/aanbod/woningaanbod/breda/koop/huis-1001-zonnelaan-12/">
          <div class="adr addressInfo notranslate">
            <h3 class="street-address">Zonnelaan 12</h3>
            <span class="zipcity">
              <span class="postal-code">4811 AA</span>
              <span class="locality">Breda</span>
            </span>
          </div>
          <span class="price">
            <span class="kenmerk first koopprijs">
              <span class="kenmerkName">Vraagprijs</span>
              <span class="kenmerkValue">&euro; 425.000,- k.k.</span>
            </span>
          </span>
          <span class="objectstatusbanner bannerstatustekoop">Te koop</span>
          <span>Woonhuis</span>
          <span>118 m2</span>
          <span>5 kamers</span>
          <span>3 slaapkamers</span>
        </a>
      </li>
    </ul>
    """

    result = parse_realworks_listing_page(_parser_input(html))
    qa_result = qa_parser_family_result(result)

    assert len(result.listings) == 1
    listing = result.listings[0]
    assert listing.canonical_url == "https://www.example.nl/aanbod/woningaanbod/breda/koop/huis-1001-zonnelaan-12"
    assert listing.address_raw == "Zonnelaan 12"
    assert listing.asking_price_eur == 425000
    assert listing.city == "Breda"
    assert listing.status == "beschikbaar"
    assert listing.property_type == "house"
    assert qa_result.clean_count == 1
    assert qa_result.review_count == 0
    assert qa_result.rejected_count == 0


def test_rejects_category_archive_and_service_urls() -> None:
    html = """
    <nav>
      <a href="/aanbod/woningaanbod/koop/">Koop</a>
      <a href="/aanbod/woningaanbod/koop/garage/">Garage</a>
      <a href="/aanbod/woningaanbod/open-huis/">Open huis</a>
      <a href="/aanbod/woningaanbod/archief/verkocht/">Archief</a>
      <a href="/woning-verkopen/">Woning verkopen</a>
      <a href="/woning-kopen/">Woning kopen</a>
    </nav>
    """

    result = parse_realworks_listing_page(_parser_input(html))

    assert result.listings == ()
    assert result.rejected_count == 6
    assert result.warnings == ("no_realworks_detail_urls_found",)


def test_hardening_does_not_require_oldenkotte_domain() -> None:
    html = """
    <li class="al4woning aanbodEntry odd">
      <a href="/aanbod/woningaanbod/heusden/koop/huis-2002-burchtstraat-4/">
        <h3 class="street-address">Burchtstraat 4</h3>
        <span class="locality">Heusden</span>
        <span class="price">&euro; 515.000 k.k.</span>
        <span class="objectstatusbanner">Te koop</span>
        <span>Woonhuis</span>
      </a>
    </li>
    """

    olden_result = parse_realworks_listing_page(
        _parser_input(html, domain="olden.nl", url="https://www.olden.nl/aanbod/woningaanbod")
    )
    gewoon_result = parse_realworks_listing_page(
        _parser_input(html, domain="gewoonmakelaars.nl", url="https://www.gewoonmakelaars.nl/aanbod/woningaanbod/koop")
    )

    assert olden_result.listings[0].canonical_url == (
        "https://www.olden.nl/aanbod/woningaanbod/heusden/koop/huis-2002-burchtstraat-4"
    )
    assert gewoon_result.listings[0].canonical_url == (
        "https://www.gewoonmakelaars.nl/aanbod/woningaanbod/heusden/koop/huis-2002-burchtstraat-4"
    )


def test_canonical_url_normalization_is_deterministic() -> None:
    html = """
    <li class="al4woning aanbodEntry even">
      <a href="/aanbod/woningaanbod/Breda/koop/huis-1001-Zonnelaan-12/?sort=prijs#foto">
        <h3 class="street-address">Zonnelaan 12</h3>
        <span class="locality">Breda</span>
        <span class="price">&euro; 425.000 k.k.</span>
        <span class="objectstatusbanner">Te koop</span>
        <span>Woonhuis</span>
      </a>
    </li>
    """

    result = parse_realworks_listing_page(_parser_input(html))

    assert result.listings[0].canonical_url == (
        "https://www.example.nl/aanbod/woningaanbod/Breda/koop/huis-1001-Zonnelaan-12"
    )


def test_qa_reports_explicit_review_and_reject_reasons() -> None:
    review_result = qa_parser_family_result(_result(_qa_listing(address_raw="", street="", needs_review=True)))
    rejected_result = qa_parser_family_result(_result(_qa_listing(canonical_url="")))

    assert review_result.review_count == 1
    assert review_result.review_listings[0].issues == ("listing_marked_needs_review", "missing_address")
    assert rejected_result.rejected_count == 1
    assert rejected_result.rejected_listings[0].issues == ("missing_canonical_url",)
