import os
import json
import asyncio
import subprocess
import time
import select
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple

import psycopg2
import psycopg2.extras
import config
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
try:
    from sse_starlette.sse import EventSourceResponse
except ImportError:
    # Fallback if sse-starlette is missing
    from fastapi.responses import StreamingResponse as EventSourceResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from executor import get_hub  # Lazy accessor

load_dotenv()

# SSE Broadcaster for real-time signals
class SignalBroadcaster:
    def __init__(self):
        self._subscribers: List[asyncio.Queue] = []

    async def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def publish(self, signal_data: str):
        """Broadcasts signal to all connected SSE clients."""
        for q in self._subscribers:
            await q.put(signal_data)

broadcaster = SignalBroadcaster()

async def listen_for_signals():
    """Background task to LISTEN for new signals from PostgreSQL."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("LISTEN new_signal;")
    
    print("API listening for 'new_signal' notifications...")
    
    while True:
        if select.select([conn], [], [], 5) == ([], [], []):
            # Timeout, check if still alive
            await asyncio.sleep(0.1)
        else:
            conn.poll()
            while conn.notifies:
                notify = conn.notifies.pop(0)
                print(f"Received notification: {notify.payload}")
                await broadcaster.publish(notify.payload)
        await asyncio.sleep(0.1)

CURRENT_LOGIC_VERSION = config.CURRENT_LOGIC_VERSION
CURRENT_CONFIG_VERSION = config.CURRENT_CONFIG_VERSION
DATABASE_URL = os.environ["DATABASE_URL"]
PM2_SCANNER_NAME = os.environ.get("PM2_SCANNER_NAME", "idim-scanner")
START_TS = time.time()

app = FastAPI(title="Idim Ikang API", version="1.3.0")
router = APIRouter(prefix="/api")

# Startup lifecycle for dependency initialization
@app.on_event("startup")
async def startup_event():
    try:
        hub = get_hub()
        app.state.ccxt_ok = True
        app.state.executor_ready = True
        app.state.executor_error = None
        print("Sovereign Executor initialized successfully via ccxt.")
        
        # Start background listener
        asyncio.create_task(listen_for_signals())
    except Exception as e:
        app.state.ccxt_ok = False
        app.state.executor_ready = False
        app.state.executor_error = str(e)
        print(f"Sovereign Executor initialization FAILED: {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def db_conn():
    return psycopg2.connect(DATABASE_URL)

@router.get("/health")
def health():
    return {
        "status": "online",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "logic_version": CURRENT_LOGIC_VERSION,
        "ccxt_ok": getattr(app.state, "ccxt_ok", False),
        "executor_ready": getattr(app.state, "executor_ready", False),
        "executor_error": getattr(app.state, "executor_error", None)
    }

@router.get("/status")
def status():
    with db_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT ts, pair, side, score, regime FROM signals WHERE logic_version = %s ORDER BY ts DESC LIMIT 1", (CURRENT_LOGIC_VERSION,))
        last_signal = cur.fetchone()
        
        cur.execute("SELECT ts, level, event, details FROM system_logs ORDER BY ts DESC LIMIT 1")
        last_log = cur.fetchone()
        
        # Freshness Stats
        cur.execute("SELECT MAX(funding_time) as ts FROM funding_rates")
        last_funding = cur.fetchone()
        cur.execute("SELECT MAX(timestamp) as ts FROM open_interest")
        last_oi = cur.fetchone()
        cur.execute("SELECT MAX(timestamp) as ts FROM ls_ratios")
        last_ls = cur.fetchone()
        cur.execute("SELECT COUNT(*) as count FROM signals WHERE outcome IS NULL AND logic_version = %s", (CURRENT_LOGIC_VERSION,))
        unresolved = cur.fetchone()
        
        scanner_state = "offline"
        try:
            res = subprocess.run(["pm2", "jlist"], capture_output=True, text=True)
            pm2_json = json.loads(res.stdout)
            scanner_proc = next((p for p in pm2_json if p.get("name") == PM2_SCANNER_NAME), None)
            scanner_state = scanner_proc["pm2_env"]["status"] if scanner_proc else "stopped"
        except:
            pass

    return {
        "service": "idim-api",
        "scanner_state": scanner_state,
        "uptime_seconds": round(time.time() - START_TS, 1),
        "logic_version": CURRENT_LOGIC_VERSION,
        "last_signal": last_signal,
        "last_log": last_log,
        "freshness": {
            "funding": last_funding["ts"].isoformat() if last_funding and last_funding["ts"] else None,
            "oi": last_oi["ts"].isoformat() if last_oi and last_oi["ts"] else None,
            "ls": last_ls["ts"].isoformat() if last_ls and last_ls["ts"] else None,
            "unresolved_count": unresolved["count"] if unresolved else 0
        }
    }

@router.get("/signals")
def signals(all_history: bool = Query(False)):
    with db_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        query = "SELECT * FROM signals"
        if not all_history:
            query += " WHERE logic_version = %s"
        query += " ORDER BY ts DESC LIMIT 100"
        
        if all_history:
            cur.execute(query)
        else:
            cur.execute(query, (CURRENT_LOGIC_VERSION,))
        rows = cur.fetchall()
    return {"count": len(rows), "signals": rows}

@router.get("/stats")
def stats(all_history: bool = Query(False)):
    with db_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Aggregated stats by outcome and source
        q = "SELECT outcome, execution_source, COUNT(*) as count FROM signals"
        if not all_history:
            q += " WHERE logic_version = %s"
        q += " GROUP BY outcome, execution_source"
        
        if all_history:
            cur.execute(q)
        else:
            cur.execute(q, (CURRENT_LOGIC_VERSION,))
        
        res = cur.fetchall()
        
        # Initialize stats structure
        stats_data = {
            "simulated": {"wins": 0, "losses": 0, "expired": 0, "total": 0},
            "live": {"wins": 0, "losses": 0, "expired": 0, "total": 0},
            "total": {"wins": 0, "losses": 0, "expired": 0, "total": 0}
        }
        
        for r in res:
            outcome = (r['outcome'] or 'unresolved').lower()
            source = r['execution_source'] or 'simulated'
            count = r['count']
            
            # Map granular outcomes to basic ones
            mapped_outcome = outcome
            if outcome in ['partial_win', 'live_partial']: mapped_outcome = 'wins'
            elif outcome in ['win', 'live_win']: mapped_outcome = 'wins'
            elif outcome in ['loss', 'live_loss']: mapped_outcome = 'losses'
            elif outcome == 'expired': mapped_outcome = 'expired'
            else: continue # Skip unresolved
            
            stats_data[source][mapped_outcome] += count
            stats_data["total"][mapped_outcome] += count
            
            if mapped_outcome in ['wins', 'losses']:
                stats_data[source]["total"] += count
                stats_data["total"]["total"] += count

        # Calculate rates
        def calc_rates(d):
            total = d["total"]
            d["win_rate"] = round((d["wins"] / total * 100), 2) if total > 0 else 0
            d["profit_factor"] = round(d["wins"] / d["losses"], 2) if d["losses"] > 0 else (d["wins"] if d["wins"] > 0 else 0)
            return d

        stats_data["simulated"] = calc_rates(stats_data["simulated"])
        stats_data["live"] = calc_rates(stats_data["live"])
        stats_data["total"] = calc_rates(stats_data["total"])

    return stats_data

@router.get("/stream")
async def signal_stream(request: Request):
    """SSE endpoint for real-time signal streaming."""
    async def event_generator():
        queue = await broadcaster.subscribe()
        try:
            while True:
                # Check for client disconnect
                if await request.is_disconnected():
                    break
                
                try:
                    # Wait for new signal with a timeout to allow checking for disconnect
                    data = await asyncio.wait_for(queue.get(), timeout=20.0)
                    yield {
                        "event": "new_signal",
                        "data": data,
                    }
                except asyncio.TimeoutError:
                    # Keepalive ping is handled by EventSourceResponse if configured, 
                    # but we can also yield a comment
                    yield ": ping\n\n"
        finally:
            broadcaster.unsubscribe(queue)

    return EventSourceResponse(event_generator())

@router.post("/publish_signal")
async def publish_signal(signal: dict):
    """Endpoint to publish a signal to all connected SSE clients."""
    await broadcaster.publish(json.dumps(signal))
    return {"status": "published"}

@router.get("/cell-performance")
def cell_performance(all_history: bool = Query(False)):
    with db_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        allowed_cells = [
            ("STRONG_UPTREND", 80), ("STRONG_UPTREND", 85), ("STRONG_UPTREND", 90),
            ("STRONG_DOWNTREND", 80), ("STRONG_DOWNTREND", 85)
        ]
        results = []
        for regime, bucket in allowed_cells:
            q = "SELECT outcome, COUNT(*) as c FROM signals WHERE regime = %s AND (reason_trace->>'score_bucket')::int = %s"
            params = [regime, bucket]
            if not all_history:
                q += " AND logic_version = %s"
                params.append(CURRENT_LOGIC_VERSION)
            q += " GROUP BY outcome"
            cur.execute(q, tuple(params))
            counts = {r['outcome'] if r['outcome'] else 'unresolved': r['c'] for r in cur.fetchall()}
            
            w, l = counts.get('win', 0), counts.get('loss', 0)
            wr = round(w/(w+l)*100, 1) if (w+l)>0 else 0
            pf = round(w/l, 2) if l>0 else (w if w>0 else 0)
            results.append({
                "regime": regime, "score_bucket": bucket,
                "wins": w, "losses": l, "expired": counts.get('expired', 0),
                "win_rate": wr, "profit_factor": pf
            })
    return results

# === TRADING EXECUTION ENDPOINTS ===
class TradeOrder(BaseModel):
    exchange: str
    symbol: str
    side: str
    order_type: str
    amount: float
    price: float = None
    leverage: int = None
    tp_price: float = None
    sl_price: float = None

class ClosePositionRequest(BaseModel):
    exchange: str
    symbol: str

class PanicRequest(BaseModel):
    confirm: bool

class LeverageRequest(BaseModel):
    exchange: str
    symbol: str
    leverage: int

class MarginRequest(BaseModel):
    exchange: str
    symbol: str
    mode: str  # 'isolated' or 'cross'

@router.get("/trade/exchanges")
def get_exchanges():
    try:
        hub = get_hub()
        exchanges = []
        for name, ex in hub.exchanges.items():
            exchanges.append({
                "name": name,
                "is_simulated": getattr(ex, "is_simulated", False)
            })
        return {"active_exchanges": exchanges}
    except Exception as e:
        return {"active_exchanges": [], "error": str(e)}

@router.get("/trade/balances")
def get_balances():
    hub = get_hub()
    return {"balances": hub.get_balances()}

@router.get("/trade/positions")
def get_positions():
    hub = get_hub()
    return {"positions": hub.get_active_positions()}

@router.get("/market/ticker/{exchange}/{symbol}")
def get_ticker(exchange: str, symbol: str):
    hub = get_hub()
    data = hub.get_ticker_data(exchange, symbol)
    if "error" in data:
        raise HTTPException(status_code=500, detail=data["error"])
    return data

@router.post("/trade/leverage")
def set_leverage(req: LeverageRequest):
    hub = get_hub()
    result = hub.set_leverage(req.exchange, req.symbol, req.leverage)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result

@router.post("/trade/margin")
def set_margin(req: MarginRequest):
    hub = get_hub()
    result = hub.set_margin_mode(req.exchange, req.symbol, req.mode)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result

@router.post("/trade/place")
def place_order(order: TradeOrder):
    hub = get_hub()
    
    # Handle leverage sync if provided
    if order.leverage:
        hub.set_leverage(order.exchange, order.symbol, order.leverage)
        
    # Build params for TP/SL if provided
    params = {}
    if order.tp_price:
        params['takeProfitPrice'] = order.tp_price
    if order.sl_price:
        params['stopLossPrice'] = order.sl_price

    result = hub.place_order(
        exchange_name=order.exchange,
        symbol=order.symbol,
        side=order.side,
        order_type=order.order_type,
        amount=order.amount,
        price=order.price,
        params=params
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result

@router.post("/api/trade/close")
@router.post("/trade/close")
def close_position(req: ClosePositionRequest):
    hub = get_hub()
    result = hub.close_position(req.exchange, req.symbol)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result

@router.post("/api/trade/panic")
@router.post("/trade/panic")
def panic_sell(req: PanicRequest):
    if not req.confirm:
         raise HTTPException(status_code=400, detail="Panic confirmation missing")
    hub = get_hub()
    return hub.panic_sell_all()

# === REGISTER ROUTES ===
app.include_router(router)

# === FALLBACK UI SERVING ===
# Serve the built Vite frontend if the static dist folder exists
dist_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dist"))
if os.path.isdir(dist_path):
    app.mount("/", StaticFiles(directory=dist_path, html=True), name="static")
