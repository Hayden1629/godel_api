# Godel Terminal API

A Selenium-based API for interacting with the Godel Terminal to extract data programmatically.

## Overview

This API allows you to automate interactions with the Godel Terminal. Essentially the idea is you type in the command you would type in the terminal and it returns a JSON object with all relevant data. For use with AI agents and model building. The main bread and butter of the code is parsing information out of the HTML that makes up the components. I will depricate this tool when Martin releases a real API.

## Usage

Use the cli.py file for commandline usage with Agentic AI. Use the main.py for running as a human person/ debugging.
You probably should log in if you want all functions to work. Additionally, you need a blank layout named "dev" 

Currently I have only written the methods for DES with more to come.

## License

MIT LICENSE