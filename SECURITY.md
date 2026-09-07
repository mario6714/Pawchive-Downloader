# Security Policy

## 1. Supported Versions

Security updates and bug fixes are maintained on a best-effort basis for the current major/minor release stream only. Older, deprecated, or third-party forked versions do not receive patches.

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0.0 | :x:                |

Users are strongly encouraged to always run the latest available release published under [Releases](https://github.com/whyamihere773/Pawchive-Downloader/releases).

---

## 2. Reporting a Security Vulnerability

If you discover a potential security vulnerability in Pawchive Downloader, I appreciate your assistance in disclosing it responsibly.

### How to Report
- **GitHub Private Vulnerability Reporting (Preferred)**: Submit an advisory directly via the repository's [Security Advisories](https://github.com/whyamihere773/Pawchive-Downloader/security/advisories) tab.
- **Issues (Non-Critical / General Inquiries)**: For non-sensitive questions or general security discussions, you may open a standard GitHub Issue labeled `security`.

### What to Include in Your Report
To help me evaluate and address the issue efficiently, please include:
- A detailed description of the vulnerability and its potential impact.
- Clear step-by-step instructions or a minimal Proof of Concept (PoC) to reproduce the behavior.
- The operating system, Python version, and application release version where the behavior was observed.
- Any suggested remediation or patches, if available.

### Disclosure Process & Timeline
1. **Acknowledgement**: I aim to acknowledge receipt of genuine reports within 5–7 business days (as a solo developer, response times may vary depending on availability).
2. **Assessment**: I will investigate and determine the validity, severity, and feasibility of a patch.
3. **Resolution**: If confirmed, a fix will be developed and released in an upcoming update. I kindly ask researchers to allow reasonable time for a patch before public disclosure.

---

## 3. Scope

### In-Scope
- Vulnerabilities in the core application logic (e.g. path traversal, unsafe file deserialization, command injection).
- Insecure storage or leakage of locally saved credentials (session cookies, API keys).
- Arbitrary code execution resulting from unvalidated post or attachment metadata.

### Out-of-Scope
- **Third-Party Services**: Vulnerabilities or service outages on external websites and APIs (e.g. Pawchive, Kemono, Patreon, Discord, Bunkr, Mega, or external CDNs).
- **Upstream Dependencies**: Vulnerabilities in bundled third-party tools or libraries (such as `yt-dlp`, `PySide6`, or Python runtimes) unless direct exploitation via this application is demonstrated. Upstream issues should be reported to their respective projects.
- **Local / Physical Compromise**: Scenarios requiring existing administrative access, physical access to the target machine, or malware already executing on the user's host.
- **Third-Party Platform Enforcement**: Account suspension, rate limiting, IP bans, or Cloudflare blocks imposed by external hosts or service providers.
- **Self-Inflicted Denial of Service**: Setting thread counts or concurrent connections beyond network hardware capabilities.

---

## 4. Limitation of Liability & Non-Accountability

> [!IMPORTANT]
> **READ CAREFULLY:** Pawchive Downloader is a free, open-source personal utility developed and maintained by a solo developer as an independent project for educational and personal archiving purposes.

1. **"AS-IS" Distribution**:
   Pursuant to the project's [LICENSE](LICENSE), this software is provided strictly **"AS IS"**, without warranty of any kind, express or implied, including but not limited to warranties of merchantability, fitness for a particular purpose, non-infringement, security, or uninterrupted operation.

2. **No Accountability or Legal Liability**:
   To the maximum extent permitted by applicable law, in no event shall the author, maintainer, or copyright holder be held liable for any claim, damages, losses, costs, or liabilities (whether in contract, tort, negligence, strict liability, or otherwise) arising out of or in connection with:
   - Any security vulnerability, bug, defect, or data corruption in the software.
   - Any unauthorized access, loss of data, disk corruption, or system compromise resulting from the use or inability to use this software.
   - Any actions taken by third-party website operators, hosting providers, internet service providers, or regulatory bodies related to your use of this software.
   - Any malicious modification, unauthorized fork, or repackaged binaries distributed outside the official repository release page.

3. **No Service Level Agreement (SLA)**:
   As a solo developer, I have no legal, financial, or contractual obligation to remediate, patch, or respond to reported vulnerabilities or issues within any guaranteed timeframe or at all.

4. **User Responsibility**:
   Users assume all responsibility and risk associated with running this software, managing their own login sessions/cookies, and complying with all applicable local laws, regulations, and third-party terms of service.

---

## 5. Safe Harbor

Security researchers who discover potential vulnerabilities and report them in good faith, in accordance with this policy, will be treated with courtesy. I will not pursue legal action against researchers who:
- Perform testing exclusively against their own accounts and local environments without disrupting external services.
- Do not exploit vulnerabilities to access, alter, or exfiltrate data belonging to others.
- Act in accordance with responsible disclosure practices and refrain from premature public disclosure before a reasonable resolution window.
