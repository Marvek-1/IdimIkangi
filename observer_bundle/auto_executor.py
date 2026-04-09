import os
import json
import asyncio
import select
import logging
import psycopg2
import psycopg2.extras
import config
import risk
from executor import get_hub

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ["DATABASE_URL"]

async def auto_execution_daemon():
    """
    Auto-Execution Daemon (v1.9.4):
    Listens for new signals and triggers orders based on risk checks.
    """
    conn = psycopg2.connect(DATABASE_URL)
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("LISTEN new_signal;")
    
    logger.info("Auto-Execution Daemon listening for 'new_signal' notifications...")
    
    hub = get_hub()
    
    while True:
        if select.select([conn], [], [], 5) == ([], [], []):
            await asyncio.sleep(0.1)
        else:
            conn.poll()
            while conn.notifies:
                notify = conn.notifies.pop(0)
                try:
                    signal = json.loads(notify.payload)
                    logger.info(f"[AUTO_EXEC] Processing signal: {signal['pair']} {signal['side']} Score: {signal['score']}")
                    
                    # 1. Circuit Breaker Check
                    if not risk.check_circuit_breakers():
                        logger.warning(f"[AUTO_EXEC] Circuit breaker HALTED execution for {signal['pair']}.")
                        continue
                        
                    # 2. Deduplication Check
                    if not risk.deduplicate_signal(signal['pair'], signal['side']):
                        logger.info(f"[AUTO_EXEC] Deduplication SKIPPED execution for {signal['pair']}.")
                        continue
                        
                    # 3. Dynamic Dispatch Check (v1.9.4)
                    if not config.ENABLE_LIVE_TRADING:
                        logger.info(f"[AUTO_EXEC] Live trading DISABLED. SIMULATING execution for {signal['pair']}.")
                        # Fall through to place_order which handles simulation internally
                        
                    # 4. Extract Position Size and Attach SL/TP (v1.9.5)
                    # Use position_size from scanner's risk calculation
                    amount = signal.get('reason_trace', {}).get('position_size', 0)
                    if amount <= 0:
                        logger.error(f"[AUTO_EXEC] Invalid position size for {signal['pair']}: {amount}. SKIPPING.")
                        continue

                    logger.info(f"[AUTO_EXEC] Dispatching {signal['side']} {amount} {signal['pair']} with SL: {signal['stop_loss']} TP: {signal['take_profit']}")
                    
                    res = hub.place_order(
                        exchange_name="BINANCE", # Default exchange
                        symbol=signal['pair'],
                        side=signal['side'],
                        order_type="MARKET",
                        amount=amount,
                        params={
                            "stopLossPrice": signal['stop_loss'],
                            "takeProfitPrice": signal['take_profit']
                        }
                    )
                    
                    if res['success']:
                        logger.info(f"[AUTO_EXEC] Order DISPATCHED: {res['order_id']}")
                        # Record execution in DB (Truth Ladder Level 3)
                        try:
                            with psycopg2.connect(DATABASE_URL) as conn, conn.cursor() as cur:
                                cur.execute("""
                                    UPDATE signals 
                                    SET execution_id = %s, 
                                        execution_source = 'live',
                                        exchange_status = 'open',
                                        updated_at = NOW()
                                    WHERE signal_id = %s
                                """, (res['order_id'], signal['signal_id']))
                                conn.commit()
                        except Exception as e:
                            logger.error(f"[AUTO_EXEC] Failed to update signal with execution_id: {e}")
                    else:
                        logger.error(f"[AUTO_EXEC] Order FAILED: {res['error']}")
                        
                except Exception as e:
                    logger.error(f"Error in auto-execution loop: {e}")
                    
        await asyncio.sleep(0.1)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(auto_execution_daemon())
