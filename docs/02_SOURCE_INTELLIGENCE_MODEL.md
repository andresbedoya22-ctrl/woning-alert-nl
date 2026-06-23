# Source Intelligence Model

## Definition

Source intelligence is the structured understanding of a source before parser implementation begins. It describes who the source is, where listings appear, whether access is allowed, what technical clues exist, which delivery mode is likely, and what action should happen next.

## Why it comes before parsers

- It prevents building parsers for blocked or low-value sources.
- It groups work by reusable technical patterns instead of by company name.
- It exposes whether access, legal review, or missing evidence is the real bottleneck.
- It produces measurable reports for prioritization before implementation.

## Minimum record schema

```text
source_id
source_domain
source_name
organization_type
membership_hint
province
gemeente
city_scope
homepage_url
aanbod_url
aanbod_url_status
access_status
robots_status
terms_status
blocking_status
has_login
has_captcha
has_403
has_sitemap
has_wp_json
has_json_ld
has_visible_cards
has_iframe
iframe_domain
is_funda_dependent
is_pararius_dependent
technology_signals
detected_platform
delivery_mode
delivery_mode_confidence
parser_family_candidate
config_required
config_path
estimated_listing_count
koop_signal
huur_signal
commercial_signal
project_signal
quality_score
recommended_action
priority_score
evidence
last_reviewed_at
notes
```

## Expected reports

- counts by `access_status`
- counts by `delivery_mode`
- counts by `parser_family_candidate`
- counts by province or gemeente coverage
- backlog of `manual_review_queue`
- priority-ranked onboarding candidates
- blocked-source census with reasons

## Priority score

`priority_score` should favor sources that are:

- likely allowed;
- likely koop-relevant;
- technically reusable through an existing family;
- likely to have meaningful inventory volume;
- low in legal or anti-bot risk;
- useful for target-area or national coverage gaps.

## Manual review queue

`manual_review_queue` contains records where evidence is insufficient or conflicting. Typical reasons:

- access policy unknown;
- delivery mode ambiguous;
- source depends on external iframe;
- robots or terms unclear;
- visible inventory exists but parser family is not obvious.

## Converting legacy data

Legacy conversion should pull from current repo assets such as source master outputs, census artifacts, platform fingerprint diagnostics, source coverage reports, and selected `properties/` metadata. Conversion must preserve evidence and never pretend a legacy field is policy-approved if the original artifact did not prove that.
