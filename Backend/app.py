from flask import Flask, render_template, request, session, jsonify
from pathlib import Path
from datetime import datetime, timezone
import json

app = Flask(__name__,
            template_folder='../Frontend/templates',
            static_folder='../Frontend/static')
app.secret_key = 'michief-managed'
app.config['SESSION_PERMANENT'] = False

DATA_DIR = Path(__file__).resolve().parent / "data" / "sessions"
DATA_DIR.mkdir(parents=True, exist_ok=True)

def _now_iso_utc():
    return datetime.now(timezone.utc).isoformat()

def _get_session_id():
    sid = session.get("session_id")
    if not sid:
        sid = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        session["session_id"] = sid
    return sid

def _session_file(sid):
    return DATA_DIR / f"{sid}.json"

def _read_session(sid):
    f = _session_file(sid)
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

def _write_session(sid, payload):
    _session_file(sid).write_text(json.dumps(payload, indent=2), encoding="utf-8")

def _persist_session_payload():
    sid = _get_session_id()
    entry = _read_session(sid)
    entry["session_id"] = sid
    entry["updated_at"] = _now_iso_utc()
    entry["steps"] = session.get("form_steps", {})
    if "final_submission" in session:
        entry["final_submission"] = session.get("final_submission")
    _write_session(sid, entry)
    return str(_session_file(sid))

def _truthy_checked_ids(page):
    return [
        k for k, v in (page.get("checkboxes", {}) or {}).items()
        if bool(v) and k != "skipSection"
    ]

def _extract_attribute_checked_ids(checked):
    excluded_prefixes = {
        "clinicalcare",
        "systemmanagement",
        "legalobligation",
        "courtorder",
        "seriousthreat",
        "insuranceindemnity",
        "marketing",
        "operational",
        "humanresource",
        "generalinsurance",
        "unsurepurpose",
        "automaticallydeleted",
        "securelydestroyed",
        "manualdeletion",
        "uponpr",
        "deidentified",
    }

    attrs = []
    for c in checked:
        key = c.lower().split("-")[0]
        if key not in excluded_prefixes:
            attrs.append(c)
    return attrs

def _first_non_empty(mapping, default="Unsure"):
    for _, v in (mapping or {}).items():
        if isinstance(v, str) and v.strip():
            return v.strip()
        if v is not None and not isinstance(v, str):
            return str(v)
    return default

def _normalize_purpose(v):
    purpose_map = {
        "clinical care": "clinical care",
        "system management": "system management",
        "legal obligation": "legal obligation",
        "court order": "court order",
        "serious threat": "serious threat",
        "insurance / indemnity purpose": "insurance indemnity purpose",
        "insurance indemnity": "insurance indemnity purpose",
        "insurance indemnity purpose": "insurance indemnity purpose",
        "marketing": "marketing",
        "operational": "operational purpose",
        "operational purpose": "operational purpose",
        "human resource": "human resource purpose",
        "human resource purpose": "human resource purpose",
        "general insurance": "general insurance purpose",
        "general insurance purpose": "general insurance purpose",
        "unsure": "unsure",
    }

    if not v:
        return "unsure"

    if isinstance(v, list):
        normalized = []
        for item in v:
            s = str(item).strip().lower()
            mapped = purpose_map.get(s, s)
            if mapped not in normalized:
                normalized.append(mapped)
        return normalized if normalized else ["unsure"]

    s = str(v).strip().lower()
    return purpose_map.get(s, s)

def _normalize_consent(v):
    if not v:
        return "unsure"
    s = str(v).strip().lower()
    if s in {"yes", "no", "unsure"}:
        return s
    return "unsure"

def _normalize_retention(v):
    if not v:
        return "unsure"
    s = str(v).strip().lower()
    if "indefinite" in s or "indefinitely" in s:
        return "information is kept indefinitely"
    if s == "unsure":
        return "unsure"
    return str(v).strip()

def _normalize_binary(v):
    if not v:
        return "unsure"
    s = str(v).strip().lower()
    if s in {"yes", "no", "unsure"}:
        return s
    return "unsure"

def _normalize_exception(v):
    if not v:
        return "unsure"
    s = str(v).strip().lower()
    if s == "unsure":
        return "unsure"
    if s in {"no", "no, there are no special circumstances"}:
        return "no"
    return str(v).strip()

def _normalize_enforcement_from_checked(checked):
    lowered = [c.lower() for c in checked]
    if any("automaticallydeleted" in c for c in lowered):
        return "automatically deleted"
    if any("securelydestroyed" in c for c in lowered):
        return "securely destroyed"
    if any("manualdeletion" in c for c in lowered):
        return "manually deleted"
    if any("uponpr" in c for c in lowered):
        return "upon patient request"
    if any("deidentified" in c for c in lowered):
        return "de-identified"
    return "unsure"

def _collect_mhr_from_steps(steps):
    for _, page in (steps or {}).items():
        if _is_skipped(page):
            continue
        checked = _truthy_checked_ids(page)
        if any("myhealthrecord" in c.lower() or "mhr" in c.lower() for c in checked):
            return "yes"
    return "unsure"

def _extract_purpose_from_checked(checked):
    # maps purpose checkbox IDs to canonical purpose values
    purpose_id_map = {
        "clinicalcare": "clinical care",
        "systemmanagement": "system management",
        "legalobligation": "legal obligation",
        "courtorder": "court order",
        "seriousthreat": "serious threat",
        "insuranceindemnity": "insurance indemnity purpose",
        "marketing": "marketing",
        "operational": "operational purpose",
        "humanresource": "human resource purpose",
        "generalinsurance": "general insurance purpose",
        "unsurepurpose": "unsure",
    }

    extracted = []
    for c in checked:
        key = c.lower().split("-")[0]  # e.g. ClinicalCare-1B -> clinicalcare
        mapped = purpose_id_map.get(key)
        if mapped and mapped not in extracted:
            extracted.append(mapped)

    if not extracted:
        return ["unsure"]

    return extracted

def _extract_retention_fields(selects):
    suffixes = ["1A", "1B", "2A", "2B", "3A", "4A", "5A"]
    q1 = next((selects.get(f"Question1-{s}") for s in suffixes if selects.get(f"Question1-{s}")), "Unsure")
    q2 = next((selects.get(f"Question2-{s}") for s in suffixes if selects.get(f"Question2-{s}")), "Unsure")
    q3 = next((selects.get(f"Question3-{s}") for s in suffixes if selects.get(f"Question3-{s}")), None)
    if not q3:
        q3 = selects.get("Question1B", "Unsure")
    return q1, q2, q3  # (mhr_period, general_period, exception)

def _extract_essential_lessdetailed(radios):
    essential = radios.get("choice2", "unsure")
    less_detailed = radios.get("choice3", "unsure")
    return essential, less_detailed

def _category_from_step(step_key, page):
    checked = _truthy_checked_ids(page)
    attribute_checked = _extract_attribute_checked_ids(checked)
    selects = page.get("selects", {}) or {}
    radios = page.get("radios", {}) or {}

    purpose_raw = _extract_purpose_from_checked(checked)
    consent_raw = _first_non_empty(radios, "Unsure")
    essential_raw, less_detailed_raw = _extract_essential_lessdetailed(radios)
    mhr_raw, retention_raw, retention_exception_raw = _extract_retention_fields(selects)

    label = LABEL_MAP.get(step_key, step_key)

    return {
        label: [
            {"attributeCollected": attribute_checked if attribute_checked else ["none selected"]},
            {"collectionPurpose": _normalize_purpose(purpose_raw)},
            {"consent": _normalize_consent(consent_raw)},
            {"lessDetailed": _normalize_binary(less_detailed_raw)},
            {"essential": _normalize_binary(essential_raw)},
            {"retentionPeriodMHR": _normalize_retention(mhr_raw)},
            {"retentionPeriod": _normalize_retention(retention_raw)},
            {"retentionException": _normalize_exception(retention_exception_raw)},
            {"enforcementMeasure": _normalize_enforcement_from_checked(checked)},
        ]
    }

LABEL_MAP = {
    "_DA1": "Personal Details",
    "_DA2": "Personal Sensitive Details",
    "_HA1": "Clinical Health Data",
    "_HA2": "Clinical Records & Prescriptions",
    "_GA1": "Government Health Data",
    "_CA1": "Consumer Contributed Data",
    "_CH1": "Child Health Data",
}

def _is_skipped(page):
    return bool((page.get("checkboxes") or {}).get("skipSection"))

def _skipped_category(step_key):
    label = LABEL_MAP.get(step_key, step_key)
    return {label: [{"skipped": True}]}

def _build_report_schema_from_steps(steps):
    ordered_keys = ["_DA1", "_DA2", "_HA1", "_HA2", "_GA1", "_CA1", "_CH1"]
    categories = []

    for key in ordered_keys:
        if key in (steps or {}):
            page = steps.get(key, {}) or {}
            if _is_skipped(page):
                categories.append(_skipped_category(key))
            else:
                categories.append(_category_from_step(key, page))

    # include any additional dynamic keys not in the known order
    for key, page in (steps or {}).items():
        if key not in ordered_keys:
            page = page or {}
            if _is_skipped(page):
                categories.append(_skipped_category(key))
            else:
                categories.append(_category_from_step(key, page))

    return [
        {"collectMyHealthRecord": _collect_mhr_from_steps(steps)},
        [{"personalDataAsset": categories}]
    ]

@app.route('/')
def landing():
    """Landing page"""
    return render_template('pages/landing.html')

@app.route('/privacy')
def privacy():
    """Terms & Conditions"""
    return render_template('pages/privacy.html')

@app.route('/backgroundcheck')
def backgroundcheck():
    return render_template('pages/backgroundcheck.html')

@app.route('/sub_landing')
def sub_landing():
    """Sublanding"""
    return render_template('pages/0_Sublanding.html')

@app.route('/DA1')
def DA1():
    """Personal Data Asset Questionnaire (Part 1)"""
    return render_template('pages/1A_PersonalAssetQ.html')

@app.route('/DA2')
def DA2():
    """Personal Data Asset Questionnaire (Part 2)"""
    return render_template('pages/1B_PersonalAssetQ.html')

@app.route('/HA1')
def HA1():
    """Health Data Asset Questionnaire (Part 1)"""
    return render_template('pages/2A_HealthAssetQ.html')

@app.route('/HA2')
def HA2():
    """Health Data Asset Questionnaire (Part 2)"""
    return render_template('pages/2B_HealthAssetQ.html')

@app.route('/GA1')
def GA1():
    """Government Data Asset Questionnaire (Part 1)"""
    return render_template('pages/3A_GovAssetQ.html')

@app.route('/CA1')
def CA1():
    """Consumer-Contributed Health Data Assets"""
    return render_template('pages/4A_Consumer.html')

@app.route('/CH1')
def CH1():
    """Child Health Data Assets"""
    return render_template('pages/5A_ChildHealth.html')

@app.route('/report')
def report():
    """Report"""
    return render_template('pages/report.html')

@app.route('/invalid')
def invalid():
    """Invalid"""
    return render_template('pages/invalid.html')

@app.route('/test')
def test():
    """test"""
    return render_template('pages/test.html')

@app.route('/api/latest-submission', methods=['GET'])
def latest_submission():
    files = list(DATA_DIR.glob("*.json"))
    if not files:
        return jsonify({"ok": False, "error": "No submissions found"}), 404

    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    try:
        latest = json.loads(latest_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return jsonify({"ok": False, "error": "Could not read session file"}), 500

    raw = latest.get("final_submission")
    if raw is None:
        raw = latest.get("steps", {})

    if not raw:
        return jsonify({"ok": False, "error": "No submission payload found"}), 404

    if isinstance(raw, dict) and "form_steps" in raw:
        steps = raw.get("form_steps", {})
    elif isinstance(raw, dict) and any(k.startswith("_") for k in raw.keys()):
        steps = raw
    else:
        steps = latest.get("steps", {}) if isinstance(latest.get("steps", {}), dict) else {}

    transformed = _build_report_schema_from_steps(steps)

    return jsonify({
        "ok": True,
        "session_id": latest.get("session_id"),
        "updated_at": latest.get("updated_at"),
        "data": transformed
    }), 200

@app.route('/save-step', methods=['POST'])
def save_step():
    body = request.get_json(silent=True) or {}
    page_id = body.get("pageId")
    form_data = body.get("formData", {})

    if not page_id:
        return jsonify({"ok": False, "error": "pageId is required"}), 400

    steps = session.get("form_steps", {})
    steps[page_id] = form_data
    session["form_steps"] = steps

    file_path = _persist_session_payload()

    return jsonify({
        "ok": True,
        "message": "Step saved",
        "pageId": page_id,
        "file": file_path
    }), 200

@app.route('/submit-final', methods=['POST'])
def submit_final():
    body = request.get_json(silent=True) or {}
    final_data = body.get("finalData")

    if final_data is None:
        final_data = session.get("form_steps", {})

    session["final_submission"] = final_data
    file_path = _persist_session_payload()

    return jsonify({
        "ok": True,
        "message": "Final submission saved",
        "file": file_path
    }), 200


@app.route('/clear-session', methods=['DELETE', 'POST'])
def clear_session():
    sid = session.get("session_id")
    if sid:
        f = _session_file(sid)
        if f.exists():
            f.unlink()
    session.clear()
    return jsonify({"ok": True}), 200


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port, threaded=True)
