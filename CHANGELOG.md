## 2.0.0 (2026-09-06)

### BREAKING CHANGE

- the eight methods listed above are removed. Calls to
them now raise AttributeError rather than reaching an endpoint that
returns HTTP 410. SiteSortProperty no longer accepts "CreationTime".
Request.raw is gone and _parse_response no longer takes a raw argument,
both internal.
- get_account_list(page_size=...) and get_site_list(size=...)
now raise SolarEdgeValidationError above 100 instead of silently clamping or
ignoring the limit. Validation failures raise SolarEdgeValidationError rather
than plain ValueError; it subclasses ValueError, so existing `except
ValueError` handlers still work, but `except Exception as e: type(e)` checks
will see the new class. API errors raise SolarEdgeAPIError subclasses instead
of httpx.HTTPStatusError. get_site_user_image's `hash` parameter is renamed to
`image_hash`, which breaks callers passing it by keyword. close() and aclose()
are now no-ops for an externally provided client instead of raising ValueError,
matching what __exit__ and __aexit__ already did. Ranges that exceed a limit by
a partial day are now correctly rejected.

### Feat

- remove endpoints SolarEdge withdrew in March 2026 (#111)
- library-owned exceptions and consistent argument validation (#108)

### Fix

- request-handling bugs, test suite, py.typed, ruff rule selection (#106)
- remove .svg from remaining badge URLs
- update badge URLs to remove .svg extensions

### Refactor

- **monitoring**: extract shared endpoint layer (#107)

## 1.1.1 (2025-08-31)

### Fix

- **monitoring**: Fixed incorrect strftime parsing

## 1.1.0 (2025-08-30)

### Feat

- **pyproject**: Updated project to support python >=3.10

## 1.0.0 (2025-08-28)

### BREAKING CHANGE

- Finalized all api endpoints with sync and async methods. 

## 0.5.0.dev1 (2025-08-20)

### BREAKING CHANGE

- complete refactor

### Feat

- **monitoring**: refactored monitoring to use httpx and mirrored sync/async methods
