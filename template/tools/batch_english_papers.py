#!/usr/bin/env python3
"""Batch download English papers from literature map via scansci_bridge."""
import os, sys, json, time
from pathlib import Path

# Ensure project root in path for tools.* imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

ROOT = Path(r"D:\PKB_个人知识库\raw\papers")

# English papers with known identifiers
PAPERS = [
    # cyberspace-governance
    {"domain": "cyberspace-governance", "file": "2025_Exploring_China_Cyber_Sovereignty_AI_Governance_JCSS.pdf",
     "id": "10.1007/s42001-024-00346-8", "type": "doi"},

    # platform-governance
    {"domain": "platform-governance", "file": "2025_In_Brussels_We_Trust_Platform_Regulation.pdf",
     "id": "10.1080/17579961.2025.2470588", "type": "doi"},
    {"domain": "platform-governance", "file": "2024_DMA_DSA_Effective_Enforcement_Antitrust.pdf",
     "id": "10.1093/jaenfo/jnae018", "type": "doi"},
    # Direct PDF (OA, no DOI)
    {"domain": "platform-governance", "file": "2024_Between_the_Cracks_Media_Concentration_Platform_Dependence.pdf",
     "url": "https://policyreview.info/pdf/download/1813/1439",
     "alt_url": "https://policyreview.info/articles/analysis/between-cracks-blind-spots-regulating-media-concentration",
     "type": "direct"},
    {"domain": "platform-governance", "file": "2024_Regulating_Online_Platforms_EU_DSA_DMA_PhD_TUM.pdf",
     "url": "https://mediatum.ub.tum.de/doc/1752771/1752771.pdf", "type": "direct"},

    # group-polarization
    {"domain": "group-polarization", "file": "2025_Echo_Chamber_Systematic_Review_JCSS.pdf",
     "id": "10.1007/s42001-025-00381-z", "type": "doi", "note": "already tested OK"},
    {"domain": "group-polarization", "file": "2025_Conceptualizing_Echo_Chambers_Information_Cocoons_TI.pdf",
     "id": "10.1016/j.tele.2025.102250", "type": "doi"},
    {"domain": "group-polarization", "file": "2024_From_Perils_to_Possibilities_AI_Biases_Online_Fora_arXiv.pdf",
     "id": "2403.14298", "type": "arxiv"},
    {"domain": "group-polarization", "file": "2025_Dynamics_Inequalities_Digital_Social_Networks_arXiv.pdf",
     "id": "2503.02887", "type": "arxiv"},
    {"domain": "group-polarization", "file": "2024_Polarization_Weibo_Public_Affairs_SHS.pdf",
     "url": "https://www.shs-conferences.org/articles/shsconf/pdf/2024/27/shsconf_icdeba2024_04010.pdf", "type": "direct"},
    # ScienceDirect - need to search by DOI
    {"domain": "group-polarization", "file": "2025_Opinion_Polarization_Models_Drivers_Solutions_IPM.pdf",
     "search": "Opinion polarization models drivers solutions systematic review", "type": "search"},

    # algorithmic-power
    {"domain": "algorithmic-power", "file": "2024_Algorithmic_Discrimination_Types_Regulatory_Frontiers.pdf",
     "url": "https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2024.1320277/pdf", "type": "direct"},
    {"domain": "algorithmic-power", "file": "2024_Reducing_Organizational_Inequalities_Algorithmic_Controls.pdf",
     "id": "10.1007/s44163-024-00137-0", "type": "doi"},
    {"domain": "algorithmic-power", "file": "2024_Theories_Dimensions_Algorithmic_Power_DOAJ.pdf",
     "id": "10.6092/issn.1825-9618/19863", "type": "doi"},
    {"domain": "algorithmic-power", "file": "2025_Structural_Oppression_AI_India_Data_Policy_TFSC.pdf",
     "search": "Structural oppression AI India data policy technological forecasting social change", "type": "search"},
    {"domain": "algorithmic-power", "file": "2025_Algorithmic_Governance_Urban_Mobility_TMS.pdf",
     "search": "Algorithmic governance urban mobility", "type": "search"},
]

import requests
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PKB-Literature-Bot/1.0)"}

def direct_download(url, dest, alt_url=None):
    urls_to_try = [url]
    if alt_url:
        urls_to_try.append(alt_url)
    for u in urls_to_try:
        try:
            r = requests.get(u, headers=HEADERS, timeout=60, allow_redirects=True)
            ct = r.headers.get('Content-Type', '').lower()
            if r.status_code == 200 and len(r.content) > 10000:
                # If not PDF, try extracting PDF link from HTML
                if 'pdf' in ct or u.endswith('.pdf'):
                    with open(dest, 'wb') as f:
                        f.write(r.content)
                    return True, f"OK ({len(r.content):,} bytes)"
                # HTML page - look for PDF links
                import re
                pdf_urls = re.findall(r'https?://[^"\'\s]+\.pdf[^"\'\s]*', r.text)
                for pdf_u in pdf_urls[:3]:
                    try:
                        r2 = requests.get(pdf_u, headers=HEADERS, timeout=60)
                        if r2.status_code == 200 and len(r2.content) > 10000:
                            with open(dest, 'wb') as f:
                                f.write(r2.content)
                            return True, f"PDF via HTML link ({len(r2.content):,} bytes)"
                    except:
                        pass
                return False, f"Got HTML ({len(r.text)} chars), no PDF link found"
            return False, f"HTTP {r.status_code} ({len(r.content)} bytes)"
        except Exception as e:
            continue
    return False, f"All URLs failed"

def scansci_download(identifier, dest_dir):
    from tools.scansci_bridge import download_paper
    return download_paper(identifier, str(dest_dir), strategy="fastest")

results = {"ok": [], "fail": [], "skip": []}
total = len(PAPERS)

for i, p in enumerate(PAPERS):
    domain = p["domain"]
    filename = p["file"]
    dest_dir = ROOT / domain
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename

    print(f"\n{'='*60}")
    print(f"[{i+1}/{total}] {domain}/{filename}")

    if dest.exists() and dest.stat().st_size > 10000:
        print(f"  ⏭  Already exists ({dest.stat().st_size:,} bytes)")
        results["skip"].append((domain, filename, "exists"))
        continue

    ptype = p["type"]
    ok = False
    msg = ""

    if ptype == "direct":
        url = p["url"]
        alt = p.get("alt_url")
        print(f"  📥 Direct: {url[:100]}...")
        ok, msg = direct_download(url, dest, alt_url=alt)
    elif ptype in ("doi", "arxiv"):
        identifier = p["id"]
        print(f"  📥 scansci [{ptype}]: {identifier}")
        try:
            result = scansci_download(identifier, dest_dir)
            ok = result.get("success", False)
            if ok:
                src = result.get("file", "")
                if src and Path(src).exists() and Path(src) != dest:
                    import shutil
                    shutil.copy2(src, dest)
                sz = dest.stat().st_size if dest.exists() else 0
                msg = f"{result.get('source','?')} ({sz:,} bytes)"
            else:
                msg = result.get("error", "unknown")
        except Exception as e:
            msg = f"scansci error: {e}"
    elif ptype == "search":
        query = p["search"]
        print(f"  🔍 Search: {query[:80]}...")
        try:
            from tools.scansci_bridge import search_papers, download_paper
            papers = search_papers(query, limit=3)
            if papers:
                found_doi = papers[0].get("doi", "")
                print(f"  → Found: {papers[0].get('title','?')[:80]}")
                print(f"  → DOI: {found_doi}")
                if found_doi:
                    result = download_paper(found_doi, str(dest_dir), strategy="fastest")
                    ok = result.get("success", False)
                    if ok:
                        src = result.get("file", "")
                        if src and Path(src).exists() and Path(src) != dest:
                            import shutil
                            shutil.copy2(src, dest)
                        sz = dest.stat().st_size if dest.exists() else 0
                        msg = f"search→{result.get('source','?')} ({sz:,} bytes)"
                    else:
                        msg = f"search OK but download failed: {result.get('error','?')}"
                else:
                    msg = "search found no DOI"
            else:
                msg = "search returned no results"
        except Exception as e:
            msg = f"search error: {e}"

    if ok and (not dest.exists() or dest.stat().st_size < 10000):
        ok = False
        msg = f"file too small or missing ({dest.stat().st_size if dest.exists() else 0} bytes)"

    if ok:
        print(f"  ✅ {msg}")
        results["ok"].append((domain, filename, msg))
    else:
        print(f"  ❌ {msg}")
        results["fail"].append((domain, filename, msg))

    time.sleep(0.5)  # polite delay

# Summary
print("\n" + "=" * 60)
print("BATCH ENGLISH PAPER DOWNLOAD — RESULTS")
print("=" * 60)
print(f"  ✅ Success: {len(results['ok'])}")
print(f"  ❌ Failed:  {len(results['fail'])}")
print(f"  ⏭  Skipped: {len(results['skip'])}")
print(f"  📄 Total:   {total}")
print("=" * 60)

if results["ok"]:
    print("\n✅ Downloaded:")
    for domain, f, msg in results["ok"]:
        print(f"  [{domain}] {f}")
        print(f"         {msg}")

if results["fail"]:
    print("\n❌ Failed:")
    for domain, f, msg in results["fail"]:
        print(f"  [{domain}] {f}")
        print(f"         {msg}")

# Update manifest
manifest_path = ROOT / "manifest.json"
existing = {}
if manifest_path.exists():
    try:
        existing = json.loads(manifest_path.read_text(encoding='utf-8'))
    except:
        pass

new_success = [{"domain": d, "file": f, "note": m} for d, f, m in results["ok"]]
all_success = existing.get("success", []) + new_success
existing["success"] = all_success
existing["download_time"] = time.strftime("%Y-%m-%dT%H:%M:%S")
existing["success_count"] = len(all_success)
existing["failed_count"] = existing.get("failed_count", 0) + len(results["fail"])

manifest_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"\n📋 Manifest updated: {manifest_path}")
