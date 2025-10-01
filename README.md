# Godel Terminal API

A Selenium-based API for interacting with the Godel Terminal to extract data programmatically.

## Overview

This API allows you to automate interactions with the Godel Terminal. Essentially the idea is you type in the command you would type in the terminal and it returns a JSON object with all relevant data. For use with AI agents and model building. The main bread and butter of the code is parsing information out of the HTML that makes up the components. I will depricate this tool when Martin releases a real API.

## Usage

Use the cli.py file for commandline usage with Agentic AI. Use the main.py for running as a human person/ debugging.
You probably should log in if you want all functions to work. Additionally, you need a blank layout named "dev" 

Currently I have only written the methods for DES with more to come.

## DES

Returns JSON of all the information on DES component, excluding chart.
Format:
{
  "timestamp": "",
  "window_id": "",
  "ticker": "",
  "company_info": {
    "company_name": "",
    "asset_class": "",
    "logo_url": "",
    "website": "",
    "address": "",
    "ceo": ""
  },
  "description": "",
  "eps_estimates": {
    "Q4": "",
    "FY1": "",
    "FY2": ""
  },
  "analyst_ratings": [
    {
      "Firm": "",
      "Analyst": "",
      "Rating": "",
      "Old_Target": "",
      "New_Target": "",
      "Date": ""
    }
  ],
  "snapshot": {
    "Exchange": "",
    "Currency": "",
    "Float": "",
    "Employees": "",
    "Insiders": "",
    "Institutions": "",
    "P/Sales": "",
    "P/Book": "",
    "EV/EBITDA": "",
    "EV/R": "",
    "EV": "",
    "Trl P/E": "",
    "Fwd P/E": "",
    "Trl Yld": "",
    "Fwd Yld": "",
    "5Y Avg Yld": "",
    "Payout R": "",
    "Ex Div Date": "",
    "Div Date": "",
    "Beta": "",
    "Short": "",
    "Short R": ""
  }
}

## License

MIT LICENSE