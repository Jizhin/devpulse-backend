import requests
import socket
import ssl
import re
import urllib.parse
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any, Optional
from urllib3.exceptions import InsecureRequestWarning

# Suppress only the single warning from urllib3.
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

COMMON_DIRECTORIES = [
    '/admin', '/backup', '/.git', '/.env', '/wp-admin', '/phpinfo.php',
    '/test', '/demo', '/api', '/swagger', '/docs', '/.well-known/',
    '/server-status', '/.ssh', '/config', '/db', '/database',
    '/backup.sql', '/dump.sql', '/.htaccess', '/.htpasswd',
    '/crossdomain.xml', '/clientaccesspolicy.xml'
]

COMMON_XSS_PAYLOADS = [
    '<script>alert(1)</script>',
    '"><script>alert(1)</script>',
    'javascript:alert(1)',
    'onerror=alert(1)',
]

COMMON_SQLI_PAYLOADS = [
    "'",
    "' OR '1'='1",
    "' UNION SELECT NULL--",
    "'; DROP TABLE users--",
]

def scan_target_url(target_url: str, timeout: int = 15) -> Dict[str, Any]:
    """
    Perform a comprehensive vulnerability scan on a target URL.
    Returns a dict with 'summary' and 'issues'.
    """
    issues = []
    summary = {'critical': 0, 'warning': 0, 'info': 0}
    if not target_url.startswith(('http://', 'https://')):
        target_url = 'http://' + target_url

    parsed = urllib.parse.urlparse(target_url)
    hostname = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    if parsed.scheme == 'https':
        ssl_issues = check_ssl_tls(hostname, port, timeout)
        issues.extend(ssl_issues)
        for issue in ssl_issues:
            summary[issue['severity']] += 1
    try:
        resp = requests.get(target_url, timeout=timeout, verify=False, allow_redirects=True)
        headers = resp.headers
        header_issues = check_security_headers(headers)
        issues.extend(header_issues)
        for issue in header_issues:
            summary[issue['severity']] += 1
        cookie_issues = check_cookies(resp.cookies, resp.headers.get('Set-Cookie', ''))
        issues.extend(cookie_issues)
        for issue in cookie_issues:
            summary[issue['severity']] += 1

        cors_issues = check_cors(headers)
        issues.extend(cors_issues)
        for issue in cors_issues:
            summary[issue['severity']] += 1
        csp_issues = check_csp(headers)
        issues.extend(csp_issues)
        for issue in csp_issues:
            summary[issue['severity']] += 1
        disclosure_issues = check_information_disclosure(headers, resp.text)
        issues.extend(disclosure_issues)
        for issue in disclosure_issues:
            summary[issue['severity']] += 1
        https_issues = check_https_enforcement(target_url, resp)
        issues.extend(https_issues)
        for issue in https_issues:
            summary[issue['severity']] += 1
        tech_issues = fingerprint_technology(headers, resp.text)
        issues.extend(tech_issues)
        dir_issues = enumerate_directories(base_url, timeout)
        issues.extend(dir_issues)
        for issue in dir_issues:
            summary[issue['severity']] += 1
        if '?' in target_url:
            injection_issues = test_injection(target_url, timeout)
            issues.extend(injection_issues)
            for issue in injection_issues:
                summary[issue['severity']] += 1
        else:
            form_issues = test_forms(base_url, resp.text, timeout)
            issues.extend(form_issues)
            for issue in form_issues:
                summary[issue['severity']] += 1

    except requests.exceptions.RequestException as e:
        issues.append({
            'title': 'Failed to connect to target',
            'description': f'Unable to reach the target URL: {str(e)}',
            'severity': 'critical',
            'category': 'connectivity',
            'evidence': str(e)
        })
        summary['critical'] += 1

    return {
        'summary': summary,
        'issues': issues,
        'target_url': target_url
    }


def check_ssl_tls(hostname: str, port: int, timeout: int) -> List[Dict]:
    """Check SSL/TLS configuration, certificate, and protocols."""
    issues = []
    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()

                # Check certificate expiration
                not_after = cert.get('notAfter')
                if not_after:
                    expiry = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
                    if expiry < datetime.now():
                        issues.append({
                            'title': 'SSL certificate expired',
                            'description': f'Certificate expired on {expiry.isoformat()}',
                            'severity': 'critical',
                            'category': 'ssl',
                            'evidence': f'NotAfter: {not_after}'
                        })
                    elif (expiry - datetime.now()).days < 30:
                        issues.append({
                            'title': 'SSL certificate expiring soon',
                            'description': f'Certificate will expire on {expiry.isoformat()}',
                            'severity': 'warning',
                            'category': 'ssl',
                            'evidence': f'NotAfter: {not_after}'
                        })

                # Check issuer
                issuer = dict(x[0] for x in cert.get('issuer', []))
                if 'organizationName' in issuer:
                    if any(org in issuer['organizationName'] for org in ['Let\'s Encrypt', 'Self-Signed']):
                        issues.append({
                            'title': 'Self-signed or non-trusted CA',
                            'description': f'Certificate issued by {issuer["organizationName"]}. Not trusted by default.',
                            'severity': 'warning',
                            'category': 'ssl',
                            'evidence': f'Issuer: {issuer["organizationName"]}'
                        })

        # Check for weak protocols (SSLv3, TLSv1.0, TLSv1.1)
        weak_protocols = []
        for proto, version in [('SSLv3', ssl.PROTOCOL_SSLv3), ('TLSv1', ssl.PROTOCOL_TLSv1)]:
            try:
                context = ssl.SSLContext(version)
                with socket.create_connection((hostname, port), timeout=timeout) as sock:
                    with context.wrap_socket(sock, server_hostname=hostname):
                        weak_protocols.append(proto)
            except (ssl.SSLError, ConnectionError):
                pass
        if weak_protocols:
            issues.append({
                'title': 'Weak SSL/TLS protocols enabled',
                'description': f'Server supports outdated protocols: {", ".join(weak_protocols)}. Consider disabling them.',
                'severity': 'critical',
                'category': 'ssl',
                'evidence': f'Protocols: {weak_protocols}'
            })

    except Exception as e:
        issues.append({
            'title': 'SSL/TLS check failed',
            'description': f'Could not complete SSL/TLS analysis: {str(e)}',
            'severity': 'info',
            'category': 'ssl',
            'evidence': str(e)
        })
    return issues


def check_security_headers(headers: Dict) -> List[Dict]:
    """Check for missing or misconfigured security headers."""
    issues = []
    security_headers = {
        'Strict-Transport-Security': {
            'description': 'HSTS missing – should be set to enforce HTTPS and prevent protocol downgrade attacks.',
            'severity': 'warning',
        },
        'X-Frame-Options': {
            'description': 'X-Frame-Options missing – page may be vulnerable to clickjacking.',
            'severity': 'warning',
        },
        'X-Content-Type-Options': {
            'description': 'X-Content-Type-Options missing – MIME sniffing could lead to security issues.',
            'severity': 'warning',
        },
        'Content-Security-Policy': {
            'description': 'CSP missing – helps prevent XSS and data injection attacks.',
            'severity': 'warning',
        },
        'X-XSS-Protection': {
            'description': 'X-XSS-Protection missing – older browsers may not block reflected XSS.',
            'severity': 'info',
        },
        'Referrer-Policy': {
            'description': 'Referrer-Policy missing – may leak sensitive information in referrer header.',
            'severity': 'info',
        },
        'Permissions-Policy': {
            'description': 'Permissions-Policy missing – browser features may be abused.',
            'severity': 'info',
        },
    }

    for header, config in security_headers.items():
        if header not in headers:
            issues.append({
                'title': f'Missing {header} header',
                'description': config['description'],
                'severity': config['severity'],
                'category': 'headers',
            })

    # If HSTS present, check its configuration
    if 'Strict-Transport-Security' in headers:
        hsts = headers['Strict-Transport-Security']
        if 'max-age=0' in hsts:
            issues.append({
                'title': 'HSTS set to zero max-age',
                'description': 'HSTS header has max-age=0, effectively disabling HSTS.',
                'severity': 'critical',
                'category': 'headers',
                'evidence': hsts
            })
        elif not re.search(r'max-age=\d{7,}', hsts):
            issues.append({
                'title': 'HSTS max-age too short',
                'description': 'HSTS max-age should be at least 1 year (31536000 seconds).',
                'severity': 'warning',
                'category': 'headers',
                'evidence': hsts
            })
        if 'includeSubDomains' not in hsts:
            issues.append({
                'title': 'HSTS missing includeSubDomains directive',
                'description': 'includeSubDomains ensures subdomains also enforce HTTPS.',
                'severity': 'warning',
                'category': 'headers',
                'evidence': hsts
            })
        if 'preload' not in hsts:
            issues.append({
                'title': 'HSTS missing preload directive',
                'description': 'Preload ensures browser always uses HTTPS for this domain.',
                'severity': 'info',
                'category': 'headers',
                'evidence': hsts
            })

    return issues


def check_cookies(cookies, set_cookie_header: str) -> List[Dict]:
    """Analyze cookies for security attributes."""
    issues = []
    if not cookies:
        return issues

    for cookie in cookies:
        name = cookie.name
        # We need to parse the Set-Cookie header for detailed attributes
        # Since the response may have multiple Set-Cookie headers, we'll use the header string.
        cookie_lines = set_cookie_header.split(', ')  # Not perfect, but works for simple cases
        for line in cookie_lines:
            if name in line:
                if 'Secure' not in line:
                    issues.append({
                        'title': f'Cookie "{name}" missing Secure flag',
                        'description': 'Cookie without Secure flag may be transmitted over HTTP, exposing session.',
                        'severity': 'critical',
                        'category': 'cookies',
                        'evidence': line
                    })
                if 'HttpOnly' not in line:
                    issues.append({
                        'title': f'Cookie "{name}" missing HttpOnly flag',
                        'description': 'Cookie accessible via JavaScript – increases impact of XSS.',
                        'severity': 'warning',
                        'category': 'cookies',
                        'evidence': line
                    })
                if 'SameSite' not in line:
                    issues.append({
                        'title': f'Cookie "{name}" missing SameSite attribute',
                        'description': 'SameSite helps prevent CSRF. Consider setting SameSite=Lax or Strict.',
                        'severity': 'info',
                        'category': 'cookies',
                        'evidence': line
                    })
                # Check path
                match = re.search(r'Path=([^;]+)', line)
                if not match or match.group(1) not in ('/', ''):
                    issues.append({
                        'title': f'Cookie "{name}" has restrictive Path',
                        'description': f'Cookie path limited to {match.group(1) if match else "not set"} – may not be available on all pages, but this is generally fine.',
                        'severity': 'info',
                        'category': 'cookies',
                        'evidence': line
                    })
                break
    return issues


def check_cors(headers: Dict) -> List[Dict]:
    """Analyze CORS headers for misconfigurations."""
    issues = []
    acao = headers.get('Access-Control-Allow-Origin')
    if acao:
        if acao == '*':
            issues.append({
                'title': 'Wildcard CORS allowed',
                'description': 'Access-Control-Allow-Origin: * allows any site to read responses – risky if sensitive data is exposed.',
                'severity': 'critical',
                'category': 'cors',
                'evidence': acao
            })
        # Check if credentials are allowed with non-specific origin
        acac = headers.get('Access-Control-Allow-Credentials')
        if acac and acac.lower() == 'true':
            if acao == '*':
                issues.append({
                    'title': 'Invalid CORS configuration',
                    'description': 'Credentials allowed with wildcard origin – not permitted by browsers and indicates misconfiguration.',
                    'severity': 'warning',
                    'category': 'cors',
                    'evidence': f'Origin: {acao}, Credentials: {acac}'
                })
            # If ACAO is a specific origin, it might be fine, but could still be risky if it reflects user input
            # We could check if it matches the request origin, but that requires more context.
    else:
        # CORS not present – not an issue per se, but could be mentioned.
        pass

    # Check for ACAO reflection vulnerability (if the server echoes Origin header)
    # We'll not test this automatically due to complexity.

    return issues


def check_csp(headers: Dict) -> List[Dict]:
    """Parse and analyze Content-Security-Policy header."""
    issues = []
    csp = headers.get('Content-Security-Policy')
    if not csp:
        return issues

    # Simple checks
    if 'unsafe-inline' in csp:
        issues.append({
            'title': 'CSP allows unsafe-inline',
            'description': 'unsafe-inline weakens XSS protection. Consider using nonces or hashes.',
            'severity': 'warning',
            'category': 'headers',
            'evidence': csp
        })
    if 'unsafe-eval' in csp:
        issues.append({
            'title': 'CSP allows unsafe-eval',
            'description': 'unsafe-eval can be abused for XSS. Avoid if possible.',
            'severity': 'warning',
            'category': 'headers',
            'evidence': csp
        })
    if 'default-src' not in csp and 'script-src' not in csp:
        issues.append({
            'title': 'CSP lacks script restrictions',
            'description': 'CSP does not restrict script sources, reducing its effectiveness.',
            'severity': 'info',
            'category': 'headers',
            'evidence': csp
        })
    if re.search(r'script-src[^;]*\*', csp):
        issues.append({
            'title': 'CSP allows wildcard script sources',
            'description': 'script-src with * allows scripts from any origin, weakening protection.',
            'severity': 'warning',
            'category': 'headers',
            'evidence': csp
        })
    if 'object-src' not in csp:
        issues.append({
            'title': 'CSP missing object-src directive',
            'description': 'object-src should be set to \'none\' to prevent plugin execution.',
            'severity': 'info',
            'category': 'headers',
            'evidence': csp
        })

    return issues


def check_information_disclosure(headers: Dict, body: str) -> List[Dict]:
    """Check for sensitive information disclosure in headers or body."""
    issues = []

    server = headers.get('Server')
    if server:
        issues.append({
            'title': 'Server header exposes version',
            'description': f'Server: {server} – attackers can use this information to target known vulnerabilities.',
            'severity': 'info',
            'category': 'disclosure',
            'evidence': server
        })
    x_powered = headers.get('X-Powered-By')
    if x_powered:
        issues.append({
            'title': 'X-Powered-By header exposes technology',
            'description': f'{x_powered} – may reveal underlying framework.',
            'severity': 'info',
            'category': 'disclosure',
            'evidence': x_powered
        })

    emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', body)
    if emails:
        issues.append({
            'title': 'Email addresses found in response',
            'description': f'Found {len(emails)} email address(es) in HTML. Could lead to spam or targeting.',
            'severity': 'info',
            'category': 'disclosure',
            'evidence': ', '.join(emails[:3])
        })
    ips = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', body)
    if ips:
        issues.append({
            'title': 'Internal IP addresses found',
            'description': 'IP addresses in response may reveal network topology.',
            'severity': 'warning',
            'category': 'disclosure',
            'evidence': ', '.join(ips[:3])
        })
    comments = re.findall(r'<!--(.*?)-->', body, re.DOTALL)
    sensitive_words = ['password', 'secret', 'key', 'token', 'admin', 'todo', 'fixme']
    for comment in comments:
        if any(word in comment.lower() for word in sensitive_words):
            issues.append({
                'title': 'Sensitive information in HTML comments',
                'description': f'Found comment containing potentially sensitive text: {comment[:100]}...',
                'severity': 'warning',
                'category': 'disclosure',
                'evidence': comment[:200]
            })
            break  # one is enough

    return issues


def check_https_enforcement(original_url: str, response) -> List[Dict]:
    """Check if HTTP redirects to HTTPS and HSTS is set."""
    issues = []
    if original_url.startswith('http://'):
        if response.history and any(r.status_code in (301, 302) and r.headers.get('Location', '').startswith('https') for r in response.history):
            pass
        else:
            issues.append({
                'title': 'HTTP site does not redirect to HTTPS',
                'description': 'The site is accessible over HTTP and does not redirect to HTTPS. All traffic is unencrypted.',
                'severity': 'critical',
                'category': 'encryption',
            })
    else:
        pass
    return issues


def fingerprint_technology(headers: Dict, body: str) -> List[Dict]:
    """Attempt to identify technologies used."""
    issues = []
    tech = []
    server = headers.get('Server', '')
    if server:
        tech.append(server)
    x_powered = headers.get('X-Powered-By', '')
    if x_powered:
        tech.append(x_powered)
    if re.search(r'wp-content|wp-includes', body):
        tech.append('WordPress')
    if re.search(r'Django', body) or 'csrftoken' in str(headers):
        tech.append('Django')
    if re.search(r'Laravel', body) or 'laravel_session' in str(headers):
        tech.append('Laravel')
    if 'PHPSESSID' in str(headers):
        tech.append('PHP')
    if 'ASP.NET' in server or '__VIEWSTATE' in body:
        tech.append('ASP.NET')
    if 'nginx' in server.lower():
        tech.append('nginx')
    if 'cloudflare' in server.lower():
        tech.append('Cloudflare')

    if tech:
        issues.append({
            'title': 'Technology fingerprinting',
            'description': f'Detected technologies: {", ".join(set(tech))}.',
            'severity': 'info',
            'category': 'fingerprint',
            'evidence': ', '.join(set(tech))
        })
    return issues


def enumerate_directories(base_url: str, timeout: int) -> List[Dict]:
    """Check for common sensitive directories/files."""
    issues = []
    for path in COMMON_DIRECTORIES:
        url = base_url + path
        try:
            resp = requests.get(url, timeout=timeout, verify=False, allow_redirects=False)
            if resp.status_code == 200:
                issues.append({
                    'title': f'Sensitive file/directory accessible: {path}',
                    'description': f'The URL {url} returns 200 OK. This might expose sensitive information.',
                    'severity': 'critical' if path in ['/.git', '/.env', '/backup.sql'] else 'warning',
                    'category': 'exposure',
                    'evidence': f'Status: {resp.status_code}, Content-Type: {resp.headers.get("Content-Type", "unknown")}'
                })
            elif resp.status_code in [401, 403]:
                issues.append({
                    'title': f'Sensitive file/directory requires authentication: {path}',
                    'description': f'{url} returns {resp.status_code}, indicating restricted access – good.',
                    'severity': 'info',
                    'category': 'exposure',
                    'evidence': f'Status: {resp.status_code}'
                })
        except requests.RequestException:
            continue
    return issues


def test_injection(url: str, timeout: int) -> List[Dict]:
    """Test for basic XSS and SQL injection on URL parameters."""
    issues = []
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    if not params:
        return issues

    for param, values in params.items():
        original_value = values[0] if values else ''

        for payload in COMMON_XSS_PAYLOADS:
            test_params = {param: payload}
            test_url = parsed._replace(query=urllib.parse.urlencode(test_params)).geturl()
            try:
                resp = requests.get(test_url, timeout=timeout, verify=False)
                if payload in resp.text:
                    issues.append({
                        'title': f'Potential XSS in parameter "{param}"',
                        'description': f'The parameter value appears unencoded in the response, suggesting possible XSS.',
                        'severity': 'critical',
                        'category': 'xss',
                        'evidence': f'Payload: {payload}'
                    })
                    break
            except requests.RequestException:
                continue

        for payload in COMMON_SQLI_PAYLOADS:
            test_params = {param: payload}
            test_url = parsed._replace(query=urllib.parse.urlencode(test_params)).geturl()
            try:
                resp = requests.get(test_url, timeout=timeout, verify=False)
                error_patterns = [
                    'sql', 'mysql', 'postgresql', 'oracle', 'driver',
                    'unclosed quotation mark', 'you have an error in your sql',
                    'warning: mysql', 'odbc', 'sqlite'
                ]
                lower_text = resp.text.lower()
                if any(pattern in lower_text for pattern in error_patterns):
                    issues.append({
                        'title': f'Potential SQL injection in parameter "{param}"',
                        'description': 'Database error message detected, indicating possible SQL injection.',
                        'severity': 'critical',
                        'category': 'sqli',
                        'evidence': f'Payload: {payload}'
                    })
                    break
            except requests.RequestException:
                continue

    return issues


def test_forms(base_url: str, page_body: str, timeout: int) -> List[Dict]:
    """Find forms on the page and test them with simple payloads."""
    issues = []
    form_pattern = re.compile(r'<form.*?action=["\'](.*?)["\']', re.IGNORECASE | re.DOTALL)
    forms = form_pattern.findall(page_body)

    for form_action in forms:
        if not form_action.startswith('http'):
            form_url = urllib.parse.urljoin(base_url, form_action)
        else:
            form_url = form_action
        issues.append({
            'title': 'Form detected',
            'description': f'A form was found at {form_url}. Manual testing recommended for CSRF, XSS, etc.',
            'severity': 'info',
            'category': 'forms',
            'evidence': f'Form action: {form_url}'
        })
    return issues