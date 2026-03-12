#!/usr/bin/env python3
"""
CorporateStructure - Corporate hierarchy and domain mapping for assessments
Maps parent companies, subsidiaries, and associated domains for target expansion

Usage:
  python CorporateStructure.py <company> [options]

Examples:
  python CorporateStructure.py "Instagram"       # Find parent (Meta), siblings, domains
  python CorporateStructure.py "Microsoft"       # Find all subsidiaries and domains
  python CorporateStructure.py "Slack" --context  # Output as assessment context

Assessment Use Case:
  When starting a new engagement, run this to build full attack surface:
  1. Find parent company (who owns the target)
  2. Find siblings (what else does parent own - often shared infra)
  3. Find children (what does target own - legacy systems)
  4. Map all domains for enumeration
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class CorporateEntity:
    name: str
    domains: list[str] = field(default_factory=list)
    acquisition_date: Optional[str] = None
    acquisition_price: Optional[str] = None


@dataclass
class CorporateHierarchy:
    target: str
    parent: Optional[CorporateEntity] = None
    siblings: list[CorporateEntity] = field(default_factory=list)
    children: list[CorporateEntity] = field(default_factory=list)
    all_domains: list[str] = field(default_factory=list)


@dataclass
class CorporateStructureResult:
    query: str
    timestamp: str
    hierarchy: CorporateHierarchy
    assessment_context: str = ""
    errors: list[str] = field(default_factory=list)


# Corporate ownership database
CORPORATE_REGISTRY: dict[str, dict] = {
    # Alphabet/Google family
    "alphabet": {
        "parent": None,
        "children": [
            CorporateEntity("Google", ["google.com", "googleapis.com", "gstatic.com", "googlevideo.com", "google.co.*"]),
            CorporateEntity("YouTube", ["youtube.com", "youtu.be", "ytimg.com", "ggpht.com"], "2006", "$1.65B"),
            CorporateEntity("Waze", ["waze.com"], "2013", "$1.1B"),
            CorporateEntity("Nest", ["nest.com"], "2014", "$3.2B"),
            CorporateEntity("Fitbit", ["fitbit.com"], "2021", "$2.1B"),
            CorporateEntity("Mandiant", ["mandiant.com"], "2022", "$5.4B"),
            CorporateEntity("Looker", ["looker.com"], "2020", "$2.6B"),
            CorporateEntity("DeepMind", ["deepmind.com"], "2014", "$500M"),
            CorporateEntity("Kaggle", ["kaggle.com"], "2017"),
            CorporateEntity("DoubleClick", ["doubleclick.com", "doubleclick.net"], "2008", "$3.1B"),
            CorporateEntity("Waymo", ["waymo.com"]),
            CorporateEntity("Verily", ["verily.com"]),
            CorporateEntity("Calico", ["calicolabs.com"]),
            CorporateEntity("Wing", ["wing.com"]),
            CorporateEntity("Chronicle", ["chronicle.security"]),
        ],
    },
    "google": {"parent": "Alphabet", "children": []},
    "youtube": {"parent": "Alphabet", "children": []},
    "waze": {"parent": "Alphabet", "children": []},
    "nest": {"parent": "Alphabet", "children": []},
    "fitbit": {"parent": "Alphabet", "children": []},
    "mandiant": {"parent": "Alphabet", "children": []},
    "deepmind": {"parent": "Alphabet", "children": []},
    "kaggle": {"parent": "Alphabet", "children": []},
    "waymo": {"parent": "Alphabet", "children": []},

    # Meta family
    "meta": {
        "parent": None,
        "children": [
            CorporateEntity("Facebook", ["facebook.com", "fb.com", "fbcdn.net", "fbsbx.com"]),
            CorporateEntity("Instagram", ["instagram.com", "cdninstagram.com"], "2012", "$1B"),
            CorporateEntity("WhatsApp", ["whatsapp.com", "whatsapp.net"], "2014", "$19B"),
            CorporateEntity("Oculus", ["oculus.com", "oculuscdn.com"], "2014", "$2B"),
            CorporateEntity("Giphy", ["giphy.com"], "2020", "$400M"),
            CorporateEntity("Mapillary", ["mapillary.com"], "2020"),
            CorporateEntity("Kustomer", ["kustomer.com"], "2020", "$1B"),
            CorporateEntity("Threads", ["threads.net"]),
        ],
    },
    "facebook": {"parent": "Meta", "children": []},
    "instagram": {"parent": "Meta", "children": []},
    "whatsapp": {"parent": "Meta", "children": []},
    "oculus": {"parent": "Meta", "children": []},
    "giphy": {"parent": "Meta", "children": []},

    # Microsoft family
    "microsoft": {
        "parent": None,
        "children": [
            CorporateEntity("LinkedIn", ["linkedin.com", "licdn.com"], "2016", "$26.2B"),
            CorporateEntity("GitHub", ["github.com", "githubusercontent.com", "githubassets.com"], "2018", "$7.5B"),
            CorporateEntity("Nuance", ["nuance.com"], "2021", "$19.7B"),
            CorporateEntity("Activision Blizzard", ["activision.com", "blizzard.com", "battle.net", "king.com"], "2023", "$68.7B"),
            CorporateEntity("Mojang", ["minecraft.net", "mojang.com"], "2014", "$2.5B"),
            CorporateEntity("ZeniMax", ["bethesda.net", "zenimax.com"], "2021", "$7.5B"),
            CorporateEntity("Skype", ["skype.com"], "2011", "$8.5B"),
            CorporateEntity("Yammer", ["yammer.com"], "2012", "$1.2B"),
            CorporateEntity("Xamarin", ["xamarin.com"], "2016"),
            CorporateEntity("npm", ["npmjs.com", "npmjs.org"], "2020"),
            CorporateEntity("Azure", ["azure.com", "azure.microsoft.com", "azurewebsites.net", "azureedge.net"]),
            CorporateEntity("Office 365", ["office.com", "office365.com", "outlook.com", "sharepoint.com", "onedrive.com"]),
        ],
    },
    "linkedin": {"parent": "Microsoft", "children": []},
    "github": {"parent": "Microsoft", "children": []},
    "activision": {"parent": "Microsoft", "children": []},
    "blizzard": {"parent": "Microsoft", "children": []},
    "mojang": {"parent": "Microsoft", "children": []},
    "skype": {"parent": "Microsoft", "children": []},
    "npm": {"parent": "Microsoft", "children": []},

    # Amazon family
    "amazon": {
        "parent": None,
        "children": [
            CorporateEntity("AWS", ["aws.amazon.com", "amazonaws.com", "awsstatic.com", "elasticbeanstalk.com", "cloudfront.net"]),
            CorporateEntity("Whole Foods", ["wholefoodsmarket.com"], "2017", "$13.7B"),
            CorporateEntity("Twitch", ["twitch.tv", "twitchcdn.net", "jtvnw.net"], "2014", "$970M"),
            CorporateEntity("Ring", ["ring.com"], "2018", "$1B"),
            CorporateEntity("MGM", ["mgm.com"], "2022", "$8.45B"),
            CorporateEntity("iRobot", ["irobot.com"], "2022", "$1.7B"),
            CorporateEntity("One Medical", ["onemedical.com"], "2023", "$3.9B"),
            CorporateEntity("Zappos", ["zappos.com"], "2009", "$1.2B"),
            CorporateEntity("Audible", ["audible.com"], "2008", "$300M"),
            CorporateEntity("IMDb", ["imdb.com"], "1998"),
            CorporateEntity("Goodreads", ["goodreads.com"], "2013"),
            CorporateEntity("Comixology", ["comixology.com"], "2014"),
            CorporateEntity("PillPack", ["pillpack.com"], "2018", "$753M"),
            CorporateEntity("Eero", ["eero.com"], "2019"),
        ],
    },
    "aws": {"parent": "Amazon", "children": []},
    "twitch": {"parent": "Amazon", "children": []},
    "ring": {"parent": "Amazon", "children": []},
    "wholefoodsmarket": {"parent": "Amazon", "children": []},
    "zappos": {"parent": "Amazon", "children": []},
    "audible": {"parent": "Amazon", "children": []},
    "imdb": {"parent": "Amazon", "children": []},
    "goodreads": {"parent": "Amazon", "children": []},

    # Salesforce family
    "salesforce": {
        "parent": None,
        "children": [
            CorporateEntity("Slack", ["slack.com", "slack-edge.com", "slack-imgs.com"], "2021", "$27.7B"),
            CorporateEntity("Tableau", ["tableau.com"], "2019", "$15.7B"),
            CorporateEntity("MuleSoft", ["mulesoft.com"], "2018", "$6.5B"),
            CorporateEntity("Heroku", ["heroku.com", "herokuapp.com"], "2010", "$212M"),
            CorporateEntity("ExactTarget", ["exacttarget.com"], "2013", "$2.5B"),
            CorporateEntity("Quip", ["quip.com"], "2016", "$750M"),
        ],
    },
    "slack": {"parent": "Salesforce", "children": []},
    "tableau": {"parent": "Salesforce", "children": []},
    "mulesoft": {"parent": "Salesforce", "children": []},
    "heroku": {"parent": "Salesforce", "children": []},

    # Oracle family
    "oracle": {
        "parent": None,
        "children": [
            CorporateEntity("NetSuite", ["netsuite.com"], "2016", "$9.3B"),
            CorporateEntity("Cerner", ["cerner.com"], "2022", "$28.3B"),
            CorporateEntity("Sun Microsystems", ["sun.com", "java.com", "mysql.com"], "2010", "$7.4B"),
            CorporateEntity("PeopleSoft", ["peoplesoft.com"], "2005", "$10.3B"),
            CorporateEntity("OCI", ["oraclecloud.com", "oraclecorp.com"]),
        ],
    },
    "netsuite": {"parent": "Oracle", "children": []},
    "cerner": {"parent": "Oracle", "children": []},
    "mysql": {"parent": "Oracle", "children": []},
    "java": {"parent": "Oracle", "children": []},

    # Cisco family
    "cisco": {
        "parent": None,
        "children": [
            CorporateEntity("Splunk", ["splunk.com", "splunkcloud.com"], "2024", "$28B"),
            CorporateEntity("Duo Security", ["duo.com", "duosecurity.com"], "2018", "$2.35B"),
            CorporateEntity("AppDynamics", ["appdynamics.com"], "2017", "$3.7B"),
            CorporateEntity("Webex", ["webex.com"], "2007", "$3.2B"),
            CorporateEntity("Meraki", ["meraki.com"], "2012", "$1.2B"),
            CorporateEntity("Sourcefire", ["sourcefire.com"], "2013", "$2.7B"),
        ],
    },
    "splunk": {"parent": "Cisco", "children": []},
    "duo": {"parent": "Cisco", "children": []},
    "duosecurity": {"parent": "Cisco", "children": []},
    "webex": {"parent": "Cisco", "children": []},
    "appdynamics": {"parent": "Cisco", "children": []},

    # Adobe family
    "adobe": {
        "parent": None,
        "children": [
            CorporateEntity("Figma", ["figma.com"], "2022", "$20B"),
            CorporateEntity("Magento", ["magento.com"], "2018", "$1.68B"),
            CorporateEntity("Marketo", ["marketo.com"], "2018", "$4.75B"),
            CorporateEntity("Frame.io", ["frame.io"], "2021", "$1.275B"),
            CorporateEntity("Workfront", ["workfront.com"], "2020", "$1.5B"),
        ],
    },
    "figma": {"parent": "Adobe", "children": []},
    "magento": {"parent": "Adobe", "children": []},
    "marketo": {"parent": "Adobe", "children": []},

    # IBM family
    "ibm": {
        "parent": None,
        "children": [
            CorporateEntity("Red Hat", ["redhat.com", "openshift.com", "ansible.com"], "2019", "$34B"),
            CorporateEntity("HashiCorp", ["hashicorp.com", "terraform.io", "vagrantup.com", "consul.io", "vaultproject.io"], "2024", "$6.4B"),
            CorporateEntity("Turbonomic", ["turbonomic.com"], "2021"),
            CorporateEntity("Instana", ["instana.com"], "2020"),
        ],
    },
    "redhat": {"parent": "IBM", "children": []},
    "hashicorp": {"parent": "IBM", "children": []},
    "terraform": {"parent": "IBM", "children": []},

    # Apple
    "apple": {
        "parent": None,
        "children": [
            CorporateEntity("Beats", ["beatsbydre.com"], "2014", "$3B"),
            CorporateEntity("Shazam", ["shazam.com"], "2018", "$400M"),
            CorporateEntity("Dark Sky", ["darksky.net"], "2020"),
        ],
    },
    "beats": {"parent": "Apple", "children": []},
    "shazam": {"parent": "Apple", "children": []},

    # Security vendors
    "paloaltonetworks": {
        "parent": None,
        "children": [
            CorporateEntity("Demisto", ["demisto.com"], "2019", "$560M"),
            CorporateEntity("Expanse", ["expanse.co"], "2020", "$800M"),
            CorporateEntity("Crypsis", ["crypsis.com"], "2020", "$265M"),
            CorporateEntity("Bridgecrew", ["bridgecrew.io"], "2021", "$200M"),
            CorporateEntity("Cider Security", ["cidersecurity.io"], "2022", "$300M"),
            CorporateEntity("Talon Cyber Security", ["talon-sec.com"], "2023", "$625M"),
        ],
    },
    "demisto": {"parent": "Palo Alto Networks", "children": []},
    "bridgecrew": {"parent": "Palo Alto Networks", "children": []},

    "crowdstrike": {
        "parent": None,
        "children": [
            CorporateEntity("Humio", ["humio.com"], "2021", "$400M"),
            CorporateEntity("Preempt Security", ["preemptsecurity.com"], "2020", "$96M"),
            CorporateEntity("SecureCircle", ["securecircle.com"], "2022", "$61M"),
            CorporateEntity("Reposify", ["reposify.com"], "2022"),
        ],
    },
    "humio": {"parent": "CrowdStrike", "children": []},

    # Broadcom family
    "broadcom": {
        "parent": None,
        "children": [
            CorporateEntity("VMware", ["vmware.com"], "2023", "$69B"),
            CorporateEntity("Symantec Enterprise", ["symantec.com", "broadcom.com/solutions/symantec"], "2019", "$10.7B"),
            CorporateEntity("CA Technologies", ["ca.com"], "2018", "$18.9B"),
        ],
    },
    "vmware": {
        "parent": "Broadcom",
        "children": [
            CorporateEntity("Carbon Black", ["carbonblack.com"], "2019", "$2.1B"),
            CorporateEntity("Pivotal", ["pivotal.io", "spring.io"], "2019", "$2.7B"),
            CorporateEntity("Heptio", ["heptio.com"], "2018", "$550M"),
            CorporateEntity("Tanzu", ["tanzu.vmware.com"]),
        ],
    },
    "carbonblack": {"parent": "VMware", "children": []},
    "pivotal": {"parent": "VMware", "children": []},
    "symantec": {"parent": "Broadcom", "children": []},
}


def normalize_company_name(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]", "", name.lower())
    normalized = re.sub(r"(inc|corp|llc|ltd)$", "", normalized)
    return normalized


def get_corporate_hierarchy(company_name: str) -> CorporateHierarchy:
    normalized = normalize_company_name(company_name)
    hierarchy = CorporateHierarchy(target=company_name)

    company_data = CORPORATE_REGISTRY.get(normalized)
    if not company_data:
        return hierarchy

    # Get children
    hierarchy.children = company_data.get("children", [])

    # Get parent
    parent_name = company_data.get("parent")
    if parent_name:
        parent_normalized = normalize_company_name(parent_name)
        parent_data = CORPORATE_REGISTRY.get(parent_normalized)

        parent_domains: list[str] = []
        if parent_data:
            for c in parent_data.get("children", []):
                if normalize_company_name(c.name) == parent_normalized:
                    parent_domains = c.domains
                    break

        hierarchy.parent = CorporateEntity(name=parent_name, domains=parent_domains)

        # Get siblings
        if parent_data:
            hierarchy.siblings = [
                c for c in parent_data.get("children", [])
                if normalize_company_name(c.name) != normalized
            ]

    # Collect all domains
    all_domains: set[str] = set()
    if hierarchy.parent:
        all_domains.update(hierarchy.parent.domains)
    for sibling in hierarchy.siblings:
        all_domains.update(sibling.domains)
    for child in hierarchy.children:
        all_domains.update(child.domains)

    hierarchy.all_domains = sorted(all_domains)
    return hierarchy


def generate_assessment_context(hierarchy: CorporateHierarchy) -> str:
    lines: list[str] = []

    lines.append(f"# Corporate Structure: {hierarchy.target}")
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append("")

    if hierarchy.parent:
        lines.append("## Parent Company")
        lines.append(f"- **{hierarchy.parent.name}**")
        lines.append("")

    if hierarchy.siblings:
        lines.append("## Sibling Companies (Same Parent)")
        lines.append("*Potential shared infrastructure, SSO, or internal APIs*")
        lines.append("")
        for sib in hierarchy.siblings:
            price = f" ({sib.acquisition_price})" if sib.acquisition_price else ""
            lines.append(f"### {sib.name}{price}")
            lines.append(f"Domains: {', '.join(sib.domains)}")
            lines.append("")

    if hierarchy.children:
        lines.append("## Subsidiaries / Acquisitions")
        lines.append("*Often have legacy systems, separate security teams*")
        lines.append("")
        for child in hierarchy.children:
            price = f" - {child.acquisition_price}" if child.acquisition_price else ""
            date = f" ({child.acquisition_date})" if child.acquisition_date else ""
            lines.append(f"### {child.name}{date}{price}")
            lines.append(f"Domains: {', '.join(child.domains)}")
            lines.append("")

    if hierarchy.all_domains:
        lines.append(f"## All Related Domains ({len(hierarchy.all_domains)})")
        lines.append("*For subdomain enumeration and recon*")
        lines.append("```")
        for domain in hierarchy.all_domains:
            lines.append(domain)
        lines.append("```")

    return "\n".join(lines)


def get_corporate_structure(
    company: str,
    options: Optional[dict] = None,
) -> CorporateStructureResult:
    if options is None:
        options = {}

    hierarchy = get_corporate_hierarchy(company)
    assessment_context = generate_assessment_context(hierarchy)

    result = CorporateStructureResult(
        query=company,
        timestamp=datetime.now().isoformat(),
        hierarchy=hierarchy,
        assessment_context=assessment_context,
    )

    if not hierarchy.children and not hierarchy.parent and not hierarchy.siblings:
        result.errors.append(
            f'No corporate structure data found for "{company}". '
            f"Try the parent company name, or research via Crunchbase/Wikipedia."
        )

    return result


def parse_args(args: list[str]) -> tuple[str, dict]:
    options: dict = {}
    company = ""
    i = 0

    while i < len(args):
        arg = args[i]

        if arg == "--json":
            options["json"] = True
        elif arg in ("--context", "-c"):
            options["context"] = True
        elif arg in ("--domains-only", "-d"):
            options["domains_only"] = True
        elif arg in ("-h", "--help"):
            print("""
CorporateStructure - Map corporate hierarchy for security assessments

Usage:
  python CorporateStructure.py <company> [options]

Arguments:
  company               Company name to research

Options:
  -c, --context         Output as assessment context (markdown)
  -d, --domains-only    Output only the domain list (for piping)
  --json                Output as JSON

Supported Company Families:
  Alphabet/Google, Meta/Facebook, Microsoft, Amazon, Apple,
  Salesforce, Oracle, Cisco, Adobe, IBM, VMware, Broadcom,
  Palo Alto Networks, CrowdStrike
""")
            sys.exit(0)
        else:
            if not arg.startswith("-"):
                company = arg
        i += 1

    return company, options


def _entity_to_dict(entity: CorporateEntity) -> dict:
    d: dict = {"name": entity.name, "domains": entity.domains}
    if entity.acquisition_date:
        d["acquisitionDate"] = entity.acquisition_date
    if entity.acquisition_price:
        d["acquisitionPrice"] = entity.acquisition_price
    return d


if __name__ == "__main__":
    args = sys.argv[1:]
    company, options = parse_args(args)

    if not company:
        print("Error: Company name required", file=sys.stderr)
        print("Usage: python CorporateStructure.py <company> [options]", file=sys.stderr)
        sys.exit(1)

    result = get_corporate_structure(company, options)

    if options.get("domains_only"):
        for domain in result.hierarchy.all_domains:
            print(domain)
    elif options.get("context"):
        print(result.assessment_context)
    elif options.get("json"):
        output = {
            "query": result.query,
            "timestamp": result.timestamp,
            "hierarchy": {
                "target": result.hierarchy.target,
                "parent": _entity_to_dict(result.hierarchy.parent) if result.hierarchy.parent else None,
                "siblings": [_entity_to_dict(s) for s in result.hierarchy.siblings],
                "children": [_entity_to_dict(c) for c in result.hierarchy.children],
                "allDomains": result.hierarchy.all_domains,
            },
            "assessmentContext": result.assessment_context,
            "errors": result.errors,
        }
        print(json.dumps(output, indent=2))
    else:
        h = result.hierarchy
        print(f"\nCorporate Structure: {h.target}")
        print(f"Timestamp: {result.timestamp}\n")

        if h.parent:
            print(f"Parent Company: {h.parent.name}")
            print()

        if h.siblings:
            print(f"Sibling Companies ({len(h.siblings)}):")
            print("   *Same parent - potential shared infrastructure*\n")
            for sib in h.siblings[:10]:
                print(f"   {sib.name}")
                domains_preview = ", ".join(sib.domains[:3])
                if len(sib.domains) > 3:
                    domains_preview += "..."
                print(f"     {domains_preview}")
            if len(h.siblings) > 10:
                print(f"   ... and {len(h.siblings) - 10} more")
            print()

        if h.children:
            print(f"Subsidiaries/Acquisitions ({len(h.children)}):")
            print("   *Often legacy systems, separate security teams*\n")
            for child in h.children:
                price = f" - {child.acquisition_price}" if child.acquisition_price else ""
                date = f" ({child.acquisition_date})" if child.acquisition_date else ""
                print(f"   {child.name}{date}{price}")
                print(f"     {', '.join(child.domains)}")
            print()

        print(f"Total Related Domains: {len(h.all_domains)}")

        if result.errors:
            print("\nNotes:")
            for err in result.errors:
                print(f"   {err}")

        if h.all_domains:
            print(f'\nNext steps:')
            print(f'   python CorporateStructure.py "{company}" --domains-only | head -5')
            print(f'   python CorporateStructure.py "{company}" --context > assessment-context.md')
