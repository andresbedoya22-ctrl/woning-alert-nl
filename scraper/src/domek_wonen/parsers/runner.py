from __future__ import annotations

from domek_wonen.sources.delivery_fingerprint import DeliveryFingerprintResult

from .models import ParserFamilyResult, ParserInput
from .realworks_family import RealworksParserFamily, can_parse_realworks_source


SUPPORTED_PARSER_FAMILIES = frozenset({"realworks_public"})


class ParserFamilyRunner:
    def run(
        self,
        fingerprint_result: DeliveryFingerprintResult,
        parser_input: ParserInput,
    ) -> ParserFamilyResult:
        parser_family = _result_parser_family(fingerprint_result)

        if fingerprint_result.can_proceed_to_parser_family is False:
            return _warning_result(
                parser_family=parser_family,
                parser_input=parser_input,
                warning="parser_family_not_allowed",
            )

        if fingerprint_result.parser_family_candidate not in SUPPORTED_PARSER_FAMILIES:
            return _warning_result(
                parser_family=parser_family,
                parser_input=parser_input,
                warning="unsupported_parser_family",
            )

        if not (parser_input.content or "").strip():
            return _warning_result(
                parser_family=parser_family,
                parser_input=parser_input,
                warning="empty_parser_input",
            )

        if can_parse_realworks_source(fingerprint_result):
            return RealworksParserFamily().parse_listing_page(parser_input)

        return _warning_result(
            parser_family=parser_family,
            parser_input=parser_input,
            warning="unsupported_parser_family",
        )


def run_parser_family(
    fingerprint_result: DeliveryFingerprintResult,
    parser_input: ParserInput,
) -> ParserFamilyResult:
    return ParserFamilyRunner().run(fingerprint_result, parser_input)


def _result_parser_family(fingerprint_result: DeliveryFingerprintResult) -> str:
    return fingerprint_result.parser_family_candidate or fingerprint_result.delivery_mode


def _warning_result(*, parser_family: str, parser_input: ParserInput, warning: str) -> ParserFamilyResult:
    return ParserFamilyResult(
        parser_family=parser_family,
        source_id=parser_input.source_id,
        source_domain=parser_input.source_domain,
        listings=(),
        rejected_count=0,
        warning_count=1,
        warnings=(warning,),
    )
