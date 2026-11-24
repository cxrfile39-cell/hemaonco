#!/usr/bin/env python3
"""Build one weekly issue of the Heme/Onc journal digest from PubMed.

Runs every Monday (GitHub Actions). An issue covers articles that entered
PubMed during the previous Monday-Sunday (Asia/Taipei). Output:
  docs/data/issues/<YYYY-MM-DD>.json   (issue release Monday)
  docs/data/index.json                 (list of issues, newest first)

Uses only the Python standard library. Set NCBI_API_KEY (optional) to allow
faster requests; NCBI_EMAIL (optional) identifies the tool to NCBI.
"""
import json, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
API_KEY = os.environ.get("NCBI_API_KEY", "").strip()
EMAIL = os.environ.get("NCBI_EMAIL", "").strip()
DELAY = 0.12 if API_KEY else 0.4          # NCBI: 3 req/s without key, 10 with
TPE = timezone(timedelta(hours=8))
MAX_PER_PANEL = 200


def post(endpoint, params, tries=4):
    params = dict(params, db="pubmed", retmode="json", tool="hemonc-weekly")
    if API_KEY:
        params["api_key"] = API_KEY
    if EMAIL:
        params["email"] = EMAIL
    data = urllib.parse.urlencode(params).encode()
    for i in range(tries):
        try:
            time.sleep(DELAY)
            req = urllib.request.Request(EUTILS + endpoint, data=data,
                                         headers={"User-Agent": "hemonc-weekly/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # network hiccup or 429: back off and retry
            if i == tries - 1:
                raise
            print(f"  retry {endpoint} after error: {e}", file=sys.stderr)
            time.sleep(2 * (i + 1))


def to_kw(raw):
    raw = raw.strip()
    if re.search(r"\[[a-z]+\]|\bAND\b|\bOR\b|\bNOT\b", raw):
        return f"({raw})"
    terms = [t.strip().replace('"', "") for t in re.split(r"[,，、;；\n]+", raw) if t.strip()]
    return "(" + " OR ".join(f'"{t}"[tiab]' if re.search(r"[\s\-':]", t) else f"{t}[tiab]" for t in terms) + ")"


def custom_query(c, core):
    kw = to_kw(c["query"])
    if c.get("scope", "core") == "all":
        return kw
    return "(" + " OR ".join(f'"{j}"[ta]' for j in core) + f") AND {kw}"


def issue_dates(today=None):
    today = today or datetime.now(TPE).date()
    monday = today - timedelta(days=today.weekday())
    return monday, monday - timedelta(days=7), monday - timedelta(days=1)


def search(query, start, end):
    r = post("esearch.fcgi", {"term": query, "datetype": "edat",
                              "mindate": start.strftime("%Y/%m/%d"),
                              "maxdate": end.strftime("%Y/%m/%d"),
                              "retmax": MAX_PER_PANEL, "sort": "pub_date"})
    return r.get("esearchresult", {}).get("idlist", [])


TAGS = [(r"phase\s*(iii|3)\b", "Phase III"), (r"randomi[sz]ed controlled", "RCT"),
        (r"meta-analysis", "Meta-analysis"), (r"systematic review", "Systematic review"),
        (r"guideline", "Guideline"), (r"^review$", "Review"), (r"phase\s*(ii|2)\b", "Phase II"),
        (r"^editorial$", "Editorial"), (r"^comment$", "Comment"), (r"^letter$", "Letter")]


def tags(pubtypes, title):
    out = []
    for t in pubtypes:
        for rx, label in TAGS:
            if re.search(rx, t, re.I) and label not in out:
                out.append(label)
                break
    if "Phase III" not in out and re.search(r"phase\s*(3|iii)\b", title, re.I):
        out.append("Phase III")
    if "Phase III" in out and "Phase II" in out:
        out.remove("Phase II")
    return out[:2]


GUIDE_PT = {"practice guideline", "guideline", "consensus development conference",
            "consensus development conference, nih"}
META_PT = {"meta-analysis", "systematic review", "network meta-analysis"}
REVIEW_PT = {"review", "scoping review"}


def article_type(pubtypes, title):
    """One of: orig, review, meta, guide (shown as four blocks on the page)."""
    pt = {t.lower() for t in pubtypes}
    if pt & GUIDE_PT or re.search(r"\b(guidelines?|consensus|recommendations?|position (paper|statement))\b", title, re.I):
        return "guide"
    if pt & META_PT or re.search(r"meta-analy|systematic review", title, re.I):
        return "meta"
    if pt & REVIEW_PT:
        return "review"
    return "orig"


def summaries(pmids):
    out = {}
    for i in range(0, len(pmids), 200):
        r = post("esummary.fcgi", {"id": ",".join(pmids[i:i + 200])})
        res = r.get("result", {})
        for uid in res.get("uids", []):
            d = res.get(uid, {})
            doi = next((a.get("value", "") for a in d.get("articleids", []) if a.get("idtype") == "doi"), "")
            if not doi:
                m = re.search(r"10\.\S+", d.get("elocationid", ""))
                doi = m.group(0) if m else ""
            authors = [a.get("name", "") for a in d.get("authors", []) if a.get("authtype", "Author") == "Author"]
            title = re.sub(r"<[^>]+>", "", d.get("title", "")).strip()
            date = (d.get("sortpubdate") or "")[:10].replace("/", "-")
            out[uid] = {"pmid": uid, "doi": doi, "title": title,
                        "journal": d.get("source", ""), "date": date,
                        "author": authors[0] if authors else "",
                        "tags": tags(d.get("pubtype", []), title),
                        "type": article_type(d.get("pubtype", []), title)}
    return out


def efetch_xml(pmids, tries=4):
    params = {"db": "pubmed", "retmode": "xml", "id": ",".join(pmids), "tool": "hemonc-weekly"}
    if API_KEY:
        params["api_key"] = API_KEY
    if EMAIL:
        params["email"] = EMAIL
    data = urllib.parse.urlencode(params).encode()
    for i in range(tries):
        try:
            time.sleep(DELAY)
            req = urllib.request.Request(EUTILS + "efetch.fcgi", data=data,
                                         headers={"User-Agent": "hemonc-weekly/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:
            if i == tries - 1:
                raise
            print(f"  retry efetch after error: {e}", file=sys.stderr)
            time.sleep(2 * (i + 1))


def parse_abstracts(xml_bytes):
    """PubMed efetch XML → {pmid: abstract}. 有分段標題時寫成「LABEL: 內容」，每段一行。"""
    import xml.etree.ElementTree as ET
    out = {}
    for art in ET.fromstring(xml_bytes).iter("PubmedArticle"):
        pmid = (art.findtext("MedlineCitation/PMID") or "").strip()
        parts = []
        for t in art.iterfind("MedlineCitation/Article/Abstract/AbstractText"):
            txt = " ".join("".join(t.itertext()).split())
            if not txt:
                continue
            label = (t.get("Label") or "").strip()
            parts.append(f"{label}: {txt}" if label and label.upper() != "UNLABELLED" else txt)
        if pmid:
            out[pmid] = "\n".join(parts)
    return out


def abstracts(pmids):
    out = {}
    for i in range(0, len(pmids), 150):
        try:
            out.update(parse_abstracts(efetch_xml(pmids[i:i + 150])))
        except Exception as e:  # 摘要抓不到不影響當期發行，下次執行會再補
            print(f"  ! abstracts {i}-{i + 150}: {e}", file=sys.stderr)
    return out


def fill_abstracts(arts):
    """替還沒有 abstract 欄位的文章補上摘要（沒有摘要的文章存成空字串，不會重抓）。"""
    need = [k for k, a in arts.items() if "abstract" not in a]
    if not need:
        return 0
    got = abstracts(need)
    for k in need:
        if k in got:
            arts[k]["abstract"] = got[k]
    return sum(1 for k in need if k in got)


def backfill_issues(skip=None):
    """舊期數補摘要。"""
    d = os.path.join(DOCS, "data", "issues")
    for name in sorted(os.listdir(d), reverse=True) if os.path.isdir(d) else []:
        p = os.path.join(d, name)
        if not name.endswith(".json") or name == skip:
            continue
        issue = json.load(open(p, encoding="utf-8"))
        n = fill_abstracts(issue.get("articles", {}))
        if n:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(issue, f, ensure_ascii=False, separators=(",", ":"))
            print(f"  backfilled {n} abstracts in {name}")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--abstracts-only":
        backfill_issues()
        return
    cfg = json.load(open(os.path.join(DOCS, "panels.json"), encoding="utf-8"))
    monday, start, end = issue_dates()
    if len(sys.argv) > 1:                       # optional: build a past issue, e.g. 2026-11-16
        monday, start, end = issue_dates(datetime.strptime(sys.argv[1], "%Y-%m-%d").date())
    print(f"Issue {monday}: entries {start} .. {end}")

    panels = [dict(p) for p in cfg["panels"]]
    for c in cfg.get("custom", []):
        panels.append({"id": c["id"], "set": "custom", "name": c["name"],
                       "query": custom_query(c, cfg["core_journals"])})

    lists, all_ids, failed = {}, [], []
    for p in panels:
        try:
            ids = search(p["query"], start, end)
        except Exception as e:
            print(f"  ! {p['name']}: {e}", file=sys.stderr)
            failed.append(p["id"])
            continue
        lists[p["id"]] = ids
        all_ids.extend(ids)
        print(f"  {len(ids):3d}  {p['name']}")

    if len(failed) == len(panels):
        sys.exit("Every search failed; not writing an issue.")

    arts = summaries(list(dict.fromkeys(all_ids)))
    print(f"  abstracts: {fill_abstracts(arts)}/{len(arts)}")
    for pid, ids in lists.items():   # newest first within each panel
        lists[pid] = sorted([i for i in ids if i in arts and arts[i]["title"]],
                            key=lambda i: arts[i]["date"], reverse=True)

    issue = {"issue": monday.isoformat(), "start": start.isoformat(), "end": end.isoformat(),
             "generated": datetime.now(TPE).isoformat(timespec="minutes"),
             "panels": lists, "failed": failed, "articles": arts,
             "custom": [{"id": p["id"], "name": p["name"], "query": p["query"]}
                        for p in panels if p["set"] == "custom"]}
    os.makedirs(os.path.join(DOCS, "data", "issues"), exist_ok=True)
    with open(os.path.join(DOCS, "data", "issues", f"{monday}.json"), "w", encoding="utf-8") as f:
        json.dump(issue, f, ensure_ascii=False, separators=(",", ":"))

    idx_path = os.path.join(DOCS, "data", "index.json")
    idx = json.load(open(idx_path, encoding="utf-8")) if os.path.exists(idx_path) else {"issues": []}
    issues = {i["issue"]: i for i in idx["issues"]}
    issues[monday.isoformat()] = {"issue": monday.isoformat(), "start": start.isoformat(),
                                  "end": end.isoformat(), "count": len(arts)}
    idx["issues"] = sorted(issues.values(), key=lambda i: i["issue"], reverse=True)
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=1)
    print(f"Wrote issue {monday}: {len(arts)} articles, {len(failed)} failed searches")
    backfill_issues(skip=f"{monday}.json")


if __name__ == "__main__":
    main()
