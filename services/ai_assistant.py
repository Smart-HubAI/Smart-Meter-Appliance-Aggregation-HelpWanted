"""Tata Power AI Energy Assistant — Groq Cloud backend.
Uses the groq SDK (OpenAI-compatible interface) with API key from
Windows env var GROQ_API_KEY.
"""
import os
import json
import logging
import time

# ── Load API key from Windows environment ──
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def safe_text(value, fallback):
    if value is None:
        return fallback

    txt = str(value).strip().lower()

    if txt in [
        "",
        "none",
        "null",
        "undefined",
        "nan"
    ]:
        return fallback

    return str(value)

# ── Groq client (lazy init) ──
_client = None
SELECTED_MODEL = None

# Preferred models in priority order
_PREFERRED_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
    "qwen-qwq-32b",
    "deepseek-r1-distill-llama-70b",
]


def _init_client():
    """Initialize the Groq client and select the best available model."""
    global _client, SELECTED_MODEL

    if not GROQ_API_KEY:
        logging.warning("GROQ_API_KEY not set — chatbot disabled.")
        return

    try:
        from groq import Groq
        _client = Groq(api_key=GROQ_API_KEY)

        # Probe each preferred model with a minimal call
        for model_name in _PREFERRED_MODELS:
            try:
                _client.chat.completions.create(
                    messages=[{"role": "user", "content": "ping"}],
                    model=model_name,
                    max_tokens=1,
                    temperature=0.0,
                )
                SELECTED_MODEL = model_name
                logging.info(f"Groq initialized — model: {SELECTED_MODEL}")
                return
            except Exception as probe_err:
                msg = str(probe_err).lower()
                if "rate" in msg or "429" in msg:
                    # Rate-limited but model exists — select it
                    SELECTED_MODEL = model_name
                    logging.info(f"Groq initialized (rate-limited probe) — model: {SELECTED_MODEL}")
                    return
                logging.info(f"Model '{model_name}' unavailable, trying next...")
                continue

        # Fallback: use first preferred model optimistically
        SELECTED_MODEL = _PREFERRED_MODELS[0]
        logging.warning(f"No model probe succeeded; defaulting to {SELECTED_MODEL}")

    except ImportError:
        logging.error("groq package not installed. Run: pip install groq")
    except Exception as e:
        logging.error(f"Error initializing Groq: {e}")


# Initialize on import
_init_client()


# ── System prompt ──
SYSTEM_PROMPT_TEMPLATE = """You are the Tata Power AI Energy Assistant.

Your role is to help consumers and utility administrators understand electricity
usage, billing, appliance consumption, anomalies, and energy efficiency.

CAPABILITIES:
- Explain electricity bills and tariff slabs
- Explain appliance-level energy breakdown
- Identify anomalies and tampering alerts
- Suggest practical energy-saving measures
- Compare monthly consumption trends
- Explain power factor and load factor
- Show top risky consumers (for admins)
- Summarize fleet-wide statistics (for admins)

RULES:
1. Answer ONLY using the database context provided below.
2. Never invent or fabricate numerical values.
3. If information is unavailable, state that clearly.
4. Be professional, concise, and actionable.
5. Use simple language suitable for non-technical users.
6. Never mention SQL, tables, database names, or internal implementation details.
7. Format responses with markdown where helpful (bold, bullet points).
8. When giving recommendations, prioritise the highest-impact items first.

---
DATABASE CONTEXT:
{context}
"""


# ── Groq API call ──
def _call_groq(message: str, system_instruction: str, history: list | None = None,
               max_retries: int = 3) -> str | None:
    """Call Groq with retry/backoff for rate-limit errors."""
    if not _client or not SELECTED_MODEL:
        return None

    messages = [{"role": "system", "content": system_instruction}]

    # Append conversation history (last 10 turns)
    if history:
        for msg in history[-10:]:
            role = "user" if msg.get("role") in ["user", "consumer", "admin"] else "assistant"
            messages.append({"role": role, "content": msg.get("content", "")})

    messages.append({"role": "user", "content": message})

    last_err = None
    for attempt in range(max_retries):
        try:
            completion = _client.chat.completions.create(
                messages=messages,
                model=SELECTED_MODEL,
                temperature=0.3,
                max_tokens=1024,
                top_p=0.9,
            )
            return completion.choices[0].message.content.strip()

        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            if "rate" in err_str or "429" in err_str:
                wait = 5 * (attempt + 1)
                logging.warning(f"Groq rate-limit, retrying in {wait}s...")
                time.sleep(wait)
                continue
            # Non-retryable error
            raise

    # All retries exhausted (rate-limit)
    if last_err:
        raise RuntimeError(f"Rate limit exceeded after {max_retries} retries: {last_err}")
    return None


# ── Context builders (unchanged database logic) ──

def fetch_consumer_context(consumer_id: str, message: str) -> str | None:
    """Fetch consumer data using app.py's build_consumer_dashboard."""
    try:
        from app import build_consumer_dashboard
        data = build_consumer_dashboard(consumer_id)

        overview = data.get("overview", {})
        bill = data.get("bill", {})
        carbon = data.get("carbon", {})
        ai_insights = data.get("ai_insights", {})
        appliance_breakdown = data.get("appliance_breakdown", {})
        consumer_info = data.get("consumer", {})

        context_dict = {
            "Consumer Profile": {
                "ID": consumer_info.get("consumer_id"),
                "Name": consumer_info.get("name"),
                "Category": consumer_info.get("consumer_type", "Residential"),
                "Zone": consumer_info.get("zone", "Unknown"),
            },
            "Consumption Overview": {
                "Current Month kWh": overview.get("current_month_kwh"),
                "Total Units kWh": overview.get("total_units_kwh"),
                "Daily Average kWh": overview.get("avg_daily_kwh"),
                "Energy Score": overview.get("energy_score"),
            },
            "Billing": {
                "Predicted Bill (INR)": bill.get("projected_monthly_bill"),
            },
            "Appliances Breakdown (%)": appliance_breakdown,
            "AI Insights": {
                "Top Appliance": safe_text(
                    ai_insights.get("top_appliance"),
                    "Appliance information unavailable"
                ),
                "Consumption Trend": safe_text(
                    ai_insights.get("consumption_trend"),
                    "Stable"
                ),
                "Anomaly Risk Score": ai_insights.get("anomaly_risk_score"),
                "Active Anomalies": ai_insights.get("anomaly_types_present", []),
                "Status": safe_text(
                    ai_insights.get("anomaly_status"),
                    "Normal"
                ),
                "Status Detail": safe_text(
                    ai_insights.get("anomaly_status_detail"),
                    "No active anomalies detected"
                ),
                "Energy Efficiency Insight": safe_text(
                    ai_insights.get("efficiency_insight"),
                    "No efficiency insight available"
                ),
            },
            "Carbon Footprint": carbon,
            "Recommendations": [r.get("detail") for r in data.get("recommendations", [])]
        }
        print("AI INSIGHTS:", ai_insights)
        print("OVERVIEW:", overview)
        return json.dumps(context_dict, indent=2)
    except Exception as e:
        logging.error(f"Error fetching consumer context: {e}")
        return "{}"


def fetch_admin_context(message: str) -> str | None:
    """Fetch admin summary data using util functions with granular error handling."""
    from utils.aggregations import (
        admin_monthly_energy, admin_consumer_counts, admin_tamper_stats,
        admin_avg_pf, admin_avg_load_factor, admin_active_alerts,
        admin_monthly_revenue, admin_zone_consumption_chart, admin_category_distribution
    )
    from models.risk_scoring import build_utility_investigation_queue
    
    def safe_call(func, default):
        try:
            return func()
        except Exception as e:
            logging.error(f"Error in {func.__name__}: {e}")
            return default

    me = safe_call(admin_monthly_energy, {"monthly_energy_kwh": "Error"})
    counts = safe_call(admin_consumer_counts, {"total": "Error", "connected": "Error"})
    tamper = safe_call(admin_tamper_stats, {"tamper_events": "Error", "tampered_consumers": "Error"})
    rev = safe_call(admin_monthly_revenue, {"monthly_revenue_inr": "Error"})
    avg_pf = safe_call(admin_avg_pf, "Error")
    avg_lf = safe_call(admin_avg_load_factor, "Error")
    alerts = safe_call(admin_active_alerts, "Error")
    
    try:
        zones = {z["zone"]: z["total_kwh"] for z in admin_zone_consumption_chart()}
    except Exception as e:
        logging.error(f"Error in admin_zone_consumption_chart: {e}")
        zones = {"Error": "Could not load zone data"}
        
    try:
        categories = {c["category"]: c["count"] for c in admin_category_distribution()}
    except Exception as e:
        logging.error(f"Error in admin_category_distribution: {e}")
        categories = {"Error": "Could not load category data"}

    try:
        investigation_queue = build_utility_investigation_queue(200)
        valid_risky = []
        for r in investigation_queue:
            score = r.get("overall_risk_score")
            band = r.get("risk_band")
            anomalies = r.get("anomalies", [])
            severity = r.get("severity")
            
            if severity != "Critical":
                continue # Only use exact critical threshold as defined by backend severity logic
                
            detected_issue = r.get("primary_issue", "Unknown")
            if detected_issue == "Unknown" and len(anomalies) > 0:
                detected_issue = anomalies[0].get("anomaly_type", "Unknown")
                
            rec_action = r.get("rec_action", "No Immediate Action")
            
            valid_risky.append({
                "Consumer ID": r.get("consumer_id"),
                "Risk Score": f"{score} ({band})",
                "Zone": r.get("zone", "Unknown"),
                "Detected Issue": detected_issue,
                "Recommended Action": rec_action,
                "_raw_score": score
            })
            
        valid_risky.sort(key=lambda x: x["_raw_score"], reverse=True)
        valid_risky = valid_risky[:5]
        
        for r in valid_risky:
            del r["_raw_score"]
            
        if not valid_risky:
            risky_summary = "No consumers are currently classified as High or Critical risk."
        else:
            risky_summary = valid_risky
    except Exception as e:
        logging.error(f"Error building investigation queue: {e}")
        risky_summary = "Error loading risky consumers."

    context_dict = {
        "System Summary": {
            "Total Consumers": counts.get("total"),
            "Connected Consumers": counts.get("connected"),
            "Monthly Energy (kWh)": me.get("monthly_energy_kwh"),
            "Monthly Revenue (INR)": rev.get("monthly_revenue_inr"),
        },
        "Grid Health": {
            "Average Power Factor": avg_pf,
            "Average Load Factor": avg_lf,
            "Active Alerts": alerts,
        },
        "Security & Anomalies": {
            "Tampering Events": tamper.get("tamper_events"),
            "Affected Consumers": tamper.get("tampered_consumers"),
        },
        "Zone-wise Consumption (kWh)": zones,
        "Category Distribution": categories,
        "Top 10 Risky Consumers": risky_summary
    }
    return json.dumps(context_dict, indent=2)


# ── Direct SQL responses (unchanged) ──

def check_direct_sql_response(message: str, context: str) -> str:
    """Return a canned response for common exact-match queries."""
    msg_lower = message.lower().strip().rstrip('.')
    try:
        data = json.loads(context)
    except Exception:
        return None

    if "Consumer Profile" in data:
        overview = data.get("Consumption Overview", {})
        ai = data.get("AI Insights", {})

        if msg_lower in ["what is my bill?", "what is my bill", "how much is my bill?", "why is my bill high?"]:
            bill = data.get("Billing", {}).get("Predicted Bill (INR)")
            top_app = safe_text(
                ai.get("Top Appliance"),
                "appliance information unavailable"
            )
            insight = safe_text(
                ai.get("Energy Efficiency Insight"),
                ""
            )
            return f"Your predicted electricity bill for this month is ₹{bill}. The top consuming appliance is {top_app}. {insight}" if bill else "Your billing information is currently unavailable."

        if msg_lower in ["what is my monthly consumption?", "monthly consumption"]:
            kwh = overview.get("Current Month kWh")
            return f"Your current month's consumption is {kwh} kWh." if kwh else "Your consumption data is currently unavailable."

        if msg_lower in ["which appliance consumes the most energy?", "which appliance uses the most electricity?"]:
            top_app = ai.get("Top Appliance", "unknown")
            return f"Based on our disaggregation analysis, your highest consuming appliance is the **{top_app}**."

        if msg_lower in ["how can i reduce my electricity bill?", "how can i reduce my bill?", "recommendations"]:
            recs = data.get("Recommendations", [])
            if not recs:
                return "We don't have any specific recommendations at the moment."
            return "Here are some personalized recommendations:\n" + "\n".join([f"- {r}" for r in recs])

        if msg_lower == "compare this month with last month":
            trend = safe_text(
                ai.get("Consumption Trend"),
                "Stable"
            )
            return f"Your consumption trend is currently: **{trend}**."

        if msg_lower == "explain my energy score":
            score = overview.get("Energy Score", "N/A")
            insight = safe_text(
                ai.get("Energy Efficiency Insight"),
                "Detailed score explanation unavailable."
            )
            return f"Your Energy Score is **{score}**. {insight}"

        if msg_lower == "why was i flagged?":
            anomalies = ai.get("Active Anomalies", [])
            status = safe_text(
                ai.get("Status"),
                "Normal"
            )
            detail = safe_text(
                ai.get("Status Detail"),
                "No active anomalies detected"
            )
            if not anomalies:
                return f"You currently have no active anomalies. Status: {status}."
            return f"You were flagged for: {', '.join(anomalies)}.\nStatus: {status} - {detail}"

        if msg_lower in ["show my appliance usage", "explain my appliance usage"]:
            apps = data.get("Appliances Breakdown (%)", {})
            if not apps:
                return "Appliance usage data is not available."
            res = "Here is your appliance breakdown:\n"
            for k, v in apps.items():
                if not k.startswith("_"):
                    res += f"- **{k}**: {v:.1f}%\n"
            return res

    if "System Summary" in data:
        sys_sum = data.get("System Summary", {})
        grid = data.get("Grid Health", {})
        sec = data.get("Security & Anomalies", {})

        if msg_lower in ["total consumers?", "how many consumers?"]:
            return f"There are {sys_sum.get('Total Consumers')} total consumers."

        if msg_lower in ["monthly revenue?", "what is the monthly revenue?"]:
            return f"The projected monthly revenue is ₹{sys_sum.get('Monthly Revenue (INR)')}."

        if msg_lower == "which zone consumed the most electricity?":
            zones = data.get("Zone-wise Consumption (kWh)", {})
            if not zones:
                return "Zone consumption data is unavailable."
            top_zone = max(zones.items(), key=lambda x: x[1])
            return f"The **{top_zone[0]}** zone consumed the most electricity with **{top_zone[1]:.2f} kWh**."

        if msg_lower in ["show critical consumers", "show top 10 risky consumers"]:
            risky = data.get("Top 10 Risky Consumers", [])
            
            if isinstance(risky, str):
                return risky
                
            if not risky:
                return "No consumers are currently classified as High or Critical risk."
                
            res = f"There are currently {len(risky)} Critical consumers.\n\n"
            for idx, r in enumerate(risky, start=1):
                cid = r.get('Consumer ID', 'Unknown')
                score = r.get('Risk Score', 'N/A')
                zone = r.get('Zone', 'Unknown')
                issue = r.get('Detected Issue', 'Unknown')
                rec = r.get('Recommended Action', 'None')
                
                res += f"{idx}.\n\n"
                res += f"{cid}\n\n"
                res += f"Risk Score: {score}\n\n"
                res += f"Zone: {zone}\n\n"
                res += f"Issue: {issue}\n\n"
                res += f"Recommendation:\n{rec}\n\n"
                
            return res.strip()

        if msg_lower == "summarize today's grid":
            return (f"**Grid Summary:**\n"
                    f"- Total Consumers: {sys_sum.get('Total Consumers')} ({sys_sum.get('Connected Consumers')} connected)\n"
                    f"- Average Power Factor: {grid.get('Average Power Factor')}\n"
                    f"- Average Load Factor: {grid.get('Average Load Factor')}\n"
                    f"- Active Alerts: {grid.get('Active Alerts')}")

        if msg_lower in ["show tampering statistics", "summarize active anomalies"]:
            return (f"**Tampering Statistics:**\n"
                    f"- Tampering Events: {sec.get('Tampering Events')}\n"
                    f"- Affected Consumers: {sec.get('Affected Consumers')}")

        if msg_lower == "generate today's operational report":
            return (f"**Daily Operational Report**\n\n"
                    f"**System Summary:**\n"
                    f"Monthly Energy: {sys_sum.get('Monthly Energy (kWh)')} kWh\n"
                    f"Monthly Revenue: ₹{sys_sum.get('Monthly Revenue (INR)')}\n\n"
                    f"**Grid Health:**\n"
                    f"Active Alerts: {grid.get('Active Alerts')}\n"
                    f"Average Power Factor: {grid.get('Average Power Factor')}\n\n"
                    f"**Security:**\n"
                    f"Tampering Events: {sec.get('Tampering Events')}")

        if msg_lower in ["which consumers are suspected of tampering?",
                         "show consumers suspected of tampering"]:
            tamper_events = sec.get("Tampering Events")
            affected = sec.get("Affected Consumers")
            return (f"**Tampering Overview:**\n"
                    f"- Total Tampering Events: {tamper_events}\n"
                    f"- Affected Consumers: {affected}\n"
                    f"Review the Investigation Queue for detailed consumer-level risk scores.")

    return None


def fetch_developer_context() -> str | None:
    import os, json
    
    try:
        from database.dal import get_model_metrics
        from models.evaluation import get_unified_model_metrics
        metrics = get_model_metrics()
        disagg = get_unified_model_metrics("disaggregation")
        anomaly = get_unified_model_metrics("anomaly")
        bill = get_unified_model_metrics("bill")
    except Exception as e:
        import logging
        logging.error(f"Error fetching developer metrics: {e}")
        metrics = []
        disagg = []
        anomaly = []
        bill = []
        
    # Build tree
    tree = {}
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    for root, dirs, files in os.walk(base_dir):
        # Exclude large/unnecessary dirs
        dirs[:] = [d for d in dirs if d not in (".git", "venv", "__pycache__", "node_modules", ".vscode", "artifacts", ".sixth")]
        rel_dir = os.path.relpath(root, base_dir)
        if rel_dir == ".":
            tree["/"] = [f for f in files if f.endswith(".py") or f.endswith(".md") or f.endswith(".json")]
        else:
            tree[rel_dir] = [f for f in files if f.endswith(".py") or f.endswith(".jsx") or f.endswith(".md") or f.endswith(".json") or f.endswith(".sql")]
            
    context_dict = {
        "Repository Structure": tree,
        "Machine Learning Pipeline": {
            "Disaggregation Models": disagg,
            "Anomaly Detection Models": anomaly,
            "Bill Prediction Models": bill,
        },
        "Database Architecture": "PostgreSQL database accessed via SQLAlchemy. Core models defined in database/postgres_models.py.",
        "Frontend": "React frontend located in frontend/src. Uses Framer Motion, Bootstrap, and Recharts. Connects to Flask backend via Axios.",
        "Backend": "Flask API routing in app.py. Data loaders in utils/data_loader.py."
    }
    
    return json.dumps(context_dict, indent=2)


# ── Main entry point ──

def generate_chat_response(consumer_id: str, role: str, message: str, history: list | None = None) -> str:
    """Generate a chat response. Returns answer text or 'Error: <reason>'."""

    if not GROQ_API_KEY:
        return "Error: Missing API key — set GROQ_API_KEY environment variable"

    if not SELECTED_MODEL:
        return "Error: Invalid model — no Groq model available"

    try:
        # 1. Fetch database context
        if role == "admin":
            context = fetch_admin_context(message)
        elif role == "developer":
            context = fetch_developer_context()
        else:
            context = fetch_consumer_context(consumer_id, message)

        if not context or context == "{}":
            return "Error: Context generation failed — database query returned no data"

        # 2. Try direct SQL-based response first (fast, no LLM call)
        direct_response = check_direct_sql_response(message, context)
        if direct_response:
            return direct_response

        # 3. Fall back to Groq LLM for free-form questions
        if role == "developer":
            system_instruction = "You are a Developer AI Assistant for an Energy ML project. Answer technical questions about the ML models, backend, APIs, database schema, algorithms, and repository architecture using this context. Be technical, helpful, and concise:\n" + context
        else:
            system_instruction = SYSTEM_PROMPT_TEMPLATE.format(context=context)

        try:
            result = _call_groq(message, system_instruction, history)
        except RuntimeError as groq_err:
            err = str(groq_err)
            if "401" in err or "authentication" in err.lower():
                return "Error: Authentication failed — invalid GROQ_API_KEY"
            elif "429" in err or "rate limit" in err.lower():
                return "Error: API rate limit exceeded — please try again in a moment"
            elif "timeout" in err.lower():
                return "Error: API timeout — Groq did not respond in time"
            elif "model" in err.lower() or "404" in err:
                return "Error: Invalid model — selected Groq model is unavailable"
            return f"Error: {err}"

        if result:
            return result

        return "Error: API timeout — no response received from Groq"

    except Exception as e:
        err_msg = str(e)
        logging.error(f"Unexpected chat error: {e}")
        if "database" in err_msg.lower() or "connection" in err_msg.lower():
            return "Error: Database error — could not retrieve consumer data"
        return f"Error: {err_msg}"
