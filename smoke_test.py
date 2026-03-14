#!/usr/bin/env python3
"""
EduBase smoke test – run after every deployment to verify basic functionality.

Usage:
    python smoke_test.py https://edubase.tech
    python smoke_test.py http://localhost:8000   # local dev

Exit code: 0 = all passed, 1 = one or more checks failed.

Checks performed:
  - /health/           → 200 (app is alive)
  - /                  → 200 or 302 (homepage)
  - /accounts/login/   → 200 (login page renders)
  - /admin/            → 302 redirect to login (admin exists, not 500)
  - /materialy/        → 302 redirect to login (not 500)
  - /materialy/hledat/ → 302 redirect to login (search endpoint exists)
  - /neexistujici-url/ → 404 (404 handler works)
"""

import sys
import urllib.error
import urllib.request


def _check(url: str, label: str, expected: int, follow: bool = False) -> bool:
    try:
        opener = urllib.request.build_opener()
        if not follow:
            opener = urllib.request.build_opener(
                urllib.request.HTTPRedirectHandler()
            )
            # Don't follow redirects – we want to see the raw status
            class NoRedirect(urllib.request.HTTPErrorProcessor):
                def http_response(self, request, response):
                    return response
                https_response = http_response

            opener = urllib.request.build_opener(NoRedirect)

        req = urllib.request.Request(url, headers={'User-Agent': 'EduBase-SmokeTest/1.0'})
        with opener.open(req, timeout=10) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception as exc:
        print(f'  ❌  {label:<40} ERROR: {exc}')
        return False

    ok = status == expected
    icon = '✅' if ok else '❌'
    note = '' if ok else f'  (expected {expected}, got {status})'
    print(f'  {icon}  {label:<40} HTTP {status}{note}')
    return ok


def main():
    if len(sys.argv) < 2:
        print('Usage: python smoke_test.py <base_url>')
        print('       python smoke_test.py https://edubase.tech')
        sys.exit(1)

    base = sys.argv[1].rstrip('/')
    print(f'\nEduBase smoke test → {base}\n')

    checks = [
        (_check(f'{base}/health/',                    '/health/',           200),),
        (_check(f'{base}/',                           '/',                  200),),
        (_check(f'{base}/accounts/login/',            '/accounts/login/',   200),),
        (_check(f'{base}/admin/',                     '/admin/',            302),),
        (_check(f'{base}/materialy/',                 '/materialy/',        302),),
        (_check(f'{base}/materialy/hledat/?q=test',   '/materialy/hledat/', 302),),
        (_check(f'{base}/tato-stranka-neexistuje/',   '404 handler',        404),),
    ]

    passed = sum(1 for (r,) in checks if r)
    total  = len(checks)
    print(f'\n{"─" * 50}')
    print(f'Result: {passed}/{total} checks passed')

    if passed == total:
        print('✅  All checks passed – deployment OK\n')
        sys.exit(0)
    else:
        print(f'❌  {total - passed} check(s) FAILED – investigate before going live\n')
        sys.exit(1)


if __name__ == '__main__':
    main()
