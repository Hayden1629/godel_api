# Godel Terminal API

Selenium-based API for the Godel Terminal. Type commands, get JSON back. Parses HTML from terminal components. Will deprecate when Martin releases a real API.

## Usage

`cli.py` for commandline/AI agents. `main.py` for human debugging. Log in and have a blank layout named "dev".

## Algorithm

Automated trading algo that runs during market hours. Uses MOST to get active stocks (5b+ market cap, filters low float), runs PRT analysis, picks top 5 long and 5 short by edge. Executes via Schwab API with 2% stop losses. Holds positions for 10 minutes then closes. Skips commission stocks.

Runs 1 minute after market open until 3 minutes before close. Auto-closes all positions before market close.

Trade journal saved to `trade_journal.json`. Stats sent to webhook.

## Using this tool yourself
You are going to need a schwab account to use the API. first replace the config-example file with your godel and scwab credentials. Run the get_OG_tokens.py and login to schwab. when you paste the URL it gives you into the terminal it will save the initial tokens. from there just boot up algo_loop and everything should run.

## License

MIT LICENSE