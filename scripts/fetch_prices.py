import json
from pathlib import Path

try:
    import yfinance as yf
except Exception as e:
    print("yfinance missing:", e)
    raise SystemExit(1)

SYMBOLS = ["SLV", "PAAS.TO", "SPCX", "RUM"]
OUT = Path(__file__).resolve().parent.parent / "data" / "watchlist.json"


def main():
    rows = []
    for sym in SYMBOLS:
        try:
            ticker = yf.Ticker(sym)
            price = float(ticker.fast_info.last_price)
            prev = float(ticker.fast_info.previous_close)
            change = ((price - prev) / prev * 100) if prev else 0.0
            rows.append({"symbol": sym, "price": price, "change": round(change, 2)})
            print(f"{sym}: {price:.2f} ({change:+.2f}%)")
        except Exception as e:
            print(f"error {sym}: {e}")
    OUT.write_text(json.dumps(rows, indent=2))
    print("updated", OUT)


if __name__ == "__main__":
    main()
