#!/usr/bin/env python3
"""
SecretScan - Secret Scanning CLI

Scan directories for sensitive information using TruffleHog.
Detects 700+ credential types with entropy analysis and pattern matching.
Part of PAI CORE Tools.

Usage:
  python SecretScan.py <directory>
  python SecretScan.py . --verbose
  python SecretScan.py . --verify

Options:
  --verbose: Show detailed information about each finding
  --json: Output results in JSON format
  --verify: Attempt to verify if credentials are active
"""

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class TruffleHogFinding:
    file: str
    line: int
    detector_type: str
    decoder_name: str
    verified: bool
    raw: str
    redacted: str
    extra_data: Any = None


def run_trufflehog(target_dir: str, options: list[str]) -> str:
    print(f"Running TruffleHog scan on: {target_dir}\n")
    print("This may take a moment...\n")

    try:
        result = subprocess.run(
            ["trufflehog", "filesystem", target_dir, "--json", "--no-update"] + options,
            capture_output=True,
            text=True,
        )
        # Exit code 183 = findings detected, which is not an error
        if result.returncode not in (0, 183):
            raise RuntimeError(f"TruffleHog exited with code {result.returncode}: {result.stderr}")
        return result.stdout
    except FileNotFoundError:
        raise RuntimeError("TruffleHog is not installed or not in PATH")


def parse_trufflehog_output(output: str) -> list[TruffleHogFinding]:
    findings: list[TruffleHogFinding] = []
    for line in output.strip().splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            fs_data = data.get("SourceMetadata", {}).get("Data", {}).get("Filesystem", {})
            if fs_data:
                findings.append(TruffleHogFinding(
                    file=fs_data.get("file", ""),
                    line=fs_data.get("line", 0),
                    detector_type=data.get("DetectorType", ""),
                    decoder_name=data.get("DecoderName", ""),
                    verified=data.get("Verified", False),
                    raw=data.get("Raw", ""),
                    redacted=data.get("Redacted", ""),
                    extra_data=data.get("ExtraData"),
                ))
        except json.JSONDecodeError:
            continue
    return findings


def display_finding(finding: TruffleHogFinding, verbose: bool) -> None:
    verified_str = "VERIFIED" if finding.verified else "Unverified"
    print(f"\n  {finding.file}")
    print(f"   Type: {finding.detector_type} {verified_str}")
    print(f"   Line: {finding.line}")

    if verbose:
        print(f"   Secret: {finding.redacted}")
        if finding.extra_data:
            print(f"   Details: {json.dumps(finding.extra_data, indent=2)}")

    recommendations: dict[str, str] = {
        "OpenAI": "Revoke at platform.openai.com, use OPENAI_API_KEY env var",
        "AWS": "Rotate via AWS IAM immediately, use AWS Secrets Manager",
        "GitHub": "Revoke at github.com/settings/tokens, use GitHub Secrets",
        "Stripe": "Roll key at dashboard.stripe.com, use STRIPE_SECRET_KEY env var",
        "Slack": "Revoke at api.slack.com/apps, use environment variables",
        "Google": "Revoke at console.cloud.google.com, use Secret Manager",
    }

    recommendation = "Remove from code and use secure secret management"
    for key, rec in recommendations.items():
        if key in str(finding.detector_type):
            recommendation = rec
            break

    print(f"   Fix: {recommendation}")


def format_findings(findings: list[TruffleHogFinding], verbose: bool) -> None:
    if not findings:
        print("No sensitive information found!")
        return

    print(f"Found {len(findings)} potential secret{'s' if len(findings) > 1 else ''}:\n")
    print("-" * 60)

    verified = [f for f in findings if f.verified]
    unverified = [f for f in findings if not f.verified]

    if verified:
        print("\nVERIFIED SECRETS (ACTIVE CREDENTIALS!)")
        print("-" * 60)
        for finding in verified:
            display_finding(finding, verbose)

    if unverified:
        print("\nPOTENTIAL SECRETS (Unverified)")
        print("-" * 60)
        for finding in unverified:
            display_finding(finding, verbose)

    print("\nSUMMARY & URGENT ACTIONS:")
    print("-" * 60)

    if verified:
        print("\nCRITICAL - VERIFIED ACTIVE CREDENTIALS FOUND:")
        print("1. IMMEDIATELY rotate/revoke these credentials")
        print("2. Check if these were ever pushed to a public repository")
        print("3. Audit logs for any unauthorized access")
        print("4. Move all secrets to environment variables or secret vaults")

    print("\nRECOMMENDATIONS:")
    print("1. Never commit secrets to git repositories")
    print("2. Use .env files for local development (add to .gitignore)")
    print("3. Use secret management services for production")
    print("4. Set up pre-commit hooks to prevent secret commits")
    print("5. Run: git filter-branch or BFG to remove secrets from git history")


def main() -> None:
    target_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    verbose = "--verbose" in sys.argv
    json_output = "--json" in sys.argv
    verify = "--verify" in sys.argv

    import os
    if not Path(target_dir).exists():
        print(f"Error: Directory not found: {target_dir}", file=sys.stderr)
        sys.exit(1)

    # Check if trufflehog is installed
    try:
        subprocess.run(["trufflehog", "--help"], capture_output=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("Error: TruffleHog is not installed or not in PATH", file=sys.stderr)
        print("Install with: brew install trufflehog", file=sys.stderr)
        sys.exit(1)

    try:
        options: list[str] = []
        if verify:
            options.append("--verify")

        output = run_trufflehog(target_dir, options)

        if json_output:
            print(output)
        else:
            findings = parse_trufflehog_output(output)
            format_findings(findings, verbose)

        # Exit with error code if verified secrets found
        findings = parse_trufflehog_output(output)
        if any(f.verified for f in findings):
            sys.exit(1)
    except RuntimeError as e:
        print(f"Error running TruffleHog: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
