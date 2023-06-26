import numpy as np
import pandas as pd
import json
import requests
import time
import datetime
import pathlib
from api_tokens import IEX_CLOUD_API_TOKEN


RATE_LIMITER_DURATION = 60
DAYS_TO_EXPIRE = 7
CACHE_REQUESTS = None
CACHE_DATA = "sa.csv"
BACKUP_DATA = "sa.bak.csv"
CACHE_DIR = "data_store"
TICKER_DATA = "sp_500_stocks.csv"
RESULTS_DATA = "raw_results.json"
SHEET_NAME = "Recommended Trades"
OUTPUT_FILE = "recommended_trades.xlsx"


HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:100.0) Gecko/20100101 Firefox/100.0"
}
COLUMNS = ["Ticker", "Stock Price", "Market Capitalization", "Number of Shares to Buy"]

BG_COLOR = "#0a0a23"
FONT_COLOR = "#ffffff"

STRING_STYLE = {
    "font_color": FONT_COLOR,
    "bg_color": BG_COLOR,
    "border": 1
}

PRICE_STYLE = {
    "num_format": "$0.00",
    "font_color": FONT_COLOR,
    "bg_color": BG_COLOR,
    "border": 1
}

INTEGER_STYLE = {
    "num_format": "0",
    "font_color": FONT_COLOR,
    "bg_color": BG_COLOR,
    "border": 1
}


chunk = lambda lst, n: (lst[i: i + n] for i in range(0, len(lst), n))

def get_data_from_IEX(stocks):
    symbol_groups = chunk(stocks["Ticker"], 100)
    symbol_str = [",".join(grp.values) for grp in symbol_groups]
    final_dataframe = pd.DataFrame(columns=COLUMNS)
    request_results = []
    print("Requesting data from api...")

    for sym_str in symbol_str:
        batch_api_url = f"https://api.iex.cloud/v1/data/core/quote/{sym_str}?token={IEX_CLOUD_API_TOKEN}"
        result = requests.get(batch_api_url, headers=HEADERS).json()

        for item in result:
            final_dataframe = final_dataframe.append(
                pd.Series(
                    [
                        item["symbol"],
                        item["latestPrice"],
                        item["marketCap"],
                        "N/A",
                    ],
                    index=COLUMNS,
                ),
                ignore_index=True
            )

        request_results += result
        time.sleep(RATE_LIMITER_DURATION)

    print("Data collected from api...")
    return final_dataframe, request_results

def get_portfolio_size():
    size = 0 # amount to spend on portfolio
    while size <= 0:
        portfolio_size = input("Enter the value of your portfolio:")
        try:
            size = int(portfolio_size)
            if size <= 0:
                print("Please enter a number greater than zero(0)")
        except ValueError as e:
            print("Please enter a positive integer in base 10")
        except Exception as e:
            print("Something else unexpected happened", e)
    return size

def write_to_sheet(df):
    writer = pd.ExcelWriter(OUTPUT_FILE, engine = "xlsxwriter")
    df.to_excel(writer, SHEET_NAME, index=False)

    string_format = writer.book.add_format(STRING_STYLE)
    price_format = writer.book.add_format(PRICE_STYLE)
    integer_format = writer.book.add_format(INTEGER_STYLE)

    column_formats = {
        'A': ['Ticker', string_format],
        'B': ['Stock Price', price_format],
        'C': ['Market Capitalization', price_format],
        'D': ['Number of Shares to Buy', integer_format],
    }

    for col, fmt in column_formats.items():
        writer.sheets[SHEET_NAME].set_column(f"{col}:{col}", 18, fmt[1])
    writer.save()

def main():
    final_dataframe = None
    ticker_file = pathlib.Path(CACHE_DIR).joinpath(TICKER_DATA)
    stocks = pd.read_csv(ticker_file)
    data_file = pathlib.Path(CACHE_DIR).joinpath(CACHE_DATA)

    time_delta = datetime.date.today() - datetime.date.fromtimestamp(data_file.stat().st_birthtime)
    expire_delta = datetime.timedelta(days=DAYS_TO_EXPIRE)

    
    if data_file.exists() and time_delta < expire_delta:
        # if previous data exists and is not expired
        final_dataframe = pd.read_csv(data_file, index_col=0)
    else:
        if data_file.exists():
            # if previous data exists and has expired move the data to backup
            import shutil
            shutil.move(data_file, pathlib.Path(CACHE_DIR).joinpath(BACKUP_DATA))

        final_dataframe, CACHE_REQUESTS = get_data_from_IEX(stocks)

        # write results to file to avoid calling the api again
        requests_file = pathlib.Path(CACHE_DIR).joinpath(RESULTS_DATA)
        with open(requests_file, "w") as f:
            f.write(json.dumps(CACHE_REQUESTS, indent=4))
        final_dataframe.to_csv(CACHE_DATA)
    
    portfolio_size = get_portfolio_size()
    position_size = portfolio_size / len(final_dataframe.index)
    final_dataframe.loc[:, "Number of Shares to Buy"] = \
        np.floor(position_size / final_dataframe.loc[:, "Stock Price"])
    
    write_to_sheet(final_dataframe)


if __name__ == "__main__":
    main()