#!/usr/bin/env bash
set -uo pipefail
B=https://localhost:18443
JAR=$(mktemp); ADMINJAR=$(mktemp); OUT=$(mktemp -d)
row() { printf '| %-58s | %s\n' "$1" "$2"; }
req() { # name, extra curl args...
  local name=$1; shift
  local r; r=$(curl -sk -o "$OUT/body" -D "$OUT/hdr" -w '%{http_code}' "$@")
  local loc; loc=$(rg -i '^location:' "$OUT/hdr" | tr -d '\r' | cut -d' ' -f2-)
  local ct; ct=$(rg -i '^content-type:' "$OUT/hdr" | tr -d '\r' | cut -d' ' -f2-)
  row "$name" "$r ${loc:+Location=$loc }${ct:+[$ct]}"
}
req "GET /" "$B/"
req "GET /agenda" "$B/agenda"
req "GET /agenda/" -c "$JAR" -b "$JAR" "$B/agenda/"
req "GET /login/ (root path)" "$B/login/"
req "GET /static/admin/css/base.css (root path)" "$B/static/admin/css/base.css"
req "GET /agenda/users/teacher_dashboard/ (anon)" "$B/agenda/users/teacher_dashboard/"
req "GET /agenda/login/" -c "$JAR" -b "$JAR" "$B/agenda/login/"
rg -o 'action="[^"]*"' "$OUT/body" | head -3 | sed 's/^/    login form: /'
rg -o 'href="/[^"]*"' "$OUT/body" | sort -u | sed 's/^/    link: /'
rg -i '^set-cookie:' "$OUT/hdr" | tr -d '\r' | sed 's/^/    /'
TOKEN=$(rg -o 'name="csrfmiddlewaretoken" value="[^"]+"' "$OUT/body" | head -1 | sed 's/.*value="//;s/"$//')
req "POST /agenda/login/ (CSRF, Referer+Origin)" -c "$JAR" -b "$JAR" -H "Origin: $B" -H "Referer: $B/agenda/login/" \
  --data-urlencode "csrfmiddlewaretoken=$TOKEN" --data-urlencode "username=proxyadmin" --data-urlencode "password=Proxytest-Pass-2026" "$B/agenda/login/"
rg -i '^set-cookie:' "$OUT/hdr" | tr -d '\r' | sed 's/^/    /'
req "GET /agenda/users/dashboard_redirect/" -c "$JAR" -b "$JAR" "$B/agenda/users/dashboard_redirect/"
req "GET /agenda/users/admin_dashboard/" -c "$JAR" -b "$JAR" "$B/agenda/users/admin_dashboard/"
printf '    unprefixed href/action/src/fetch: %s\n' "$(rg -c "(href|action|src)=\"/(?!agenda)|fetch\(\`/(?!agenda)" -P "$OUT/body" || echo 0)"
rg -o "fetch\(urlWithId\(\"[^\"]+\"" "$OUT/body" | head -2 | sed 's/^/    /'
rg -o 'href="/agenda/admin/"' "$OUT/body" | head -1 | sed 's/^/    /'
req "GET /agenda/admin/ (session from app login)" -c "$JAR" -b "$JAR" "$B/agenda/admin/"
rg -o 'href="[^"]*base[^"]*\.css"' "$OUT/body" | head -1 | sed 's/^/    /'
# Separate Django admin login flow.
req "GET /agenda/admin/login/" -c "$ADMINJAR" -b "$ADMINJAR" "$B/agenda/admin/login/?next=/agenda/admin/"
CSS=$(rg -o 'href="(/agenda/static/admin/css/base[^"]*\.css)"' -r '$1' "$OUT/body" | head -1)
rg -o 'action="[^"]*"' "$OUT/body" | head -1 | sed 's/^/    admin form: /'
TOKEN=$(rg -o 'name="csrfmiddlewaretoken" value="[^"]+"' "$OUT/body" | head -1 | sed 's/.*value="//;s/"$//')
req "POST /agenda/admin/login/" -c "$ADMINJAR" -b "$ADMINJAR" -H "Origin: $B" -H "Referer: $B/agenda/admin/login/" \
  --data-urlencode "csrfmiddlewaretoken=$TOKEN" --data-urlencode "username=proxyadmin" --data-urlencode "password=Proxytest-Pass-2026" --data-urlencode "next=/agenda/admin/" "$B/agenda/admin/login/?next=/agenda/admin/"
req "GET /agenda/admin/ (admin session)" -c "$ADMINJAR" -b "$ADMINJAR" "$B/agenda/admin/"
rg -o '<title>[^<]*' "$OUT/body" | head -1 | sed 's/^/    /'
req "GET $CSS" "$B$CSS"
printf '    bytes=%s cache-control=%s\n' "$(wc -c < "$OUT/body")" "$(rg -i '^cache-control:' "$OUT/hdr" | tr -d '\r' | cut -d' ' -f2-)"
req "GET /agenda/static/admin/css/base.css (unhashed)" "$B/agenda/static/admin/css/base.css"
req "GET /agenda/media/proxytest.txt" "$B/agenda/media/proxytest.txt"
printf '    body: %s\n' "$(command cat "$OUT/body")"
req "GET /agenda/media/missing.txt" "$B/agenda/media/missing.txt"
req "GET /agenda/ spoofed X-Forwarded-Host: evil.example" -H "X-Forwarded-Host: evil.example" "$B/agenda/login/"
req "GET /agenda/login/ spoofed X-Forwarded-Proto: http" -H "X-Forwarded-Proto: http" "$B/agenda/login/"
req "DIRECT app :18000 /login/ no XFP (SSL redirect)" -H "Host: localhost" "http://127.0.0.1:18000/login/"
req "DIRECT app :18000 /login/ XFP=https" -H "Host: localhost" -H "X-Forwarded-Proto: https" "http://127.0.0.1:18000/login/"
req "DIRECT app :18000 /agenda/login/ XFP=https (unstripped)" -H "Host: localhost" -H "X-Forwarded-Proto: https" "http://127.0.0.1:18000/agenda/login/"
# Logout (POST with CSRF token from a page rendered for the session).
curl -sk -c "$JAR" -b "$JAR" -o "$OUT/page" "$B/agenda/users/admin_dashboard/"
TOKEN=$(rg -o 'name="csrfmiddlewaretoken" value="[^"]+"' "$OUT/page" | head -1 | sed 's/.*value="//;s/"$//')
req "POST /agenda/logout/" -c "$JAR" -b "$JAR" -H "Origin: $B" -H "Referer: $B/agenda/users/admin_dashboard/" --data-urlencode "csrfmiddlewaretoken=$TOKEN" "$B/agenda/logout/"
rg -i '^set-cookie:' "$OUT/hdr" | tr -d '\r' | sed 's/^/    /'
req "GET /agenda/logout_success/" -c "$JAR" -b "$JAR" "$B/agenda/logout_success/"
req "GET /agenda/users/admin_dashboard/ after logout" -c "$JAR" -b "$JAR" "$B/agenda/users/admin_dashboard/"
echo "cookie jar:"; rg -v '^#|^$' "$JAR" | awk '{print "    domain="$1" path="$3" secure="$4" name="$6}'
