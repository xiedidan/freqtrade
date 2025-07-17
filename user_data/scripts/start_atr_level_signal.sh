#!/bin/sh

# Set script to exit on error
set -e

# Configuration variables
CONFIG_FILE="config_atr_signal.json"
STRATEGY="ATRLevelSignal"
EXCHANGE="binance"  # Change this to your preferred exchange
TIMEFRAME="15m"     # Matches the strategy's timeframe
DRY_RUN="true"      # Set to "false" for live trading with real money
STAKE_CURRENCY="USDT"
TELEGRAM_ENABLED="true"  # Set to "false" if you don't want Telegram notifications

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

printf "${GREEN}=== Starting FreqTrade with ATRLevelSignal Strategy ===${NC}\n"

# Check if config file exists, create if it doesn't
if [ ! -f "user_data/config/${CONFIG_FILE}" ]; then
    printf "${YELLOW}Config file not found. Creating a new one...${NC}\n"
    
    # Create config directory if it doesn't exist
    mkdir -p user_data/config
    
    # Create a basic configuration file
    cat > "user_data/config/${CONFIG_FILE}" << EOF
{
    "max_open_trades": 3,
    "stake_currency": "${STAKE_CURRENCY}",
    "stake_amount": "unlimited",
    "tradable_balance_ratio": 0.99,
    "fiat_display_currency": "USD",
    "dry_run": ${DRY_RUN},
    "dry_run_wallet": 1000,
    "cancel_open_orders_on_exit": false,
    "timeframe": "${TIMEFRAME}",
    "strategy": "${STRATEGY}",
    "exchange": {
        "name": "${EXCHANGE}",
        "key": "",
        "secret": "",
        "ccxt_config": {},
        "ccxt_async_config": {},
        "pair_whitelist": [
            "BTC/USDT",
            "ETH/USDT",
            "BNB/USDT",
            "ADA/USDT",
            "SOL/USDT",
            "XRP/USDT",
            "DOT/USDT",
            "DOGE/USDT",
            "AVAX/USDT",
            "MATIC/USDT"
        ],
        "pair_blacklist": [
            "BNB/.*"
        ]
    },
    "pairlists": [
        {"method": "StaticPairList"}
    ],
    "telegram": {
        "enabled": ${TELEGRAM_ENABLED},
        "token": "YOUR_TELEGRAM_TOKEN",
        "chat_id": "YOUR_TELEGRAM_CHAT_ID"
    },
    "api_server": {
        "enabled": true,
        "listen_ip_address": "127.0.0.1",
        "listen_port": 8080,
        "verbosity": "error",
        "jwt_secret_key": "$(openssl rand -hex 32)",
        "CORS_origins": [],
        "username": "freqtrader",
        "password": "$(openssl rand -base64 12)"
    },
    "bot_name": "atr_signal_bot",
    "initial_state": "running",
    "force_entry_enable": false,
    "internals": {
        "process_throttle_secs": 5
    }
}
EOF
    printf "${GREEN}Config file created at user_data/config/${CONFIG_FILE}${NC}\n"
    printf "${YELLOW}IMPORTANT: Please edit the config file to add your exchange API keys and Telegram credentials${NC}\n"
    printf "${YELLOW}Edit the file at: user_data/config/${CONFIG_FILE}${NC}\n"
    printf "\n"
    printf "${YELLOW}Press Enter to continue or Ctrl+C to exit and edit the config file...${NC}\n"
    read dummy
else
    printf "${GREEN}Using existing config file: user_data/config/${CONFIG_FILE}${NC}\n"
fi

# Check if we're in dry run mode
if [ "$DRY_RUN" = "true" ]; then
    printf "${YELLOW}Starting in DRY RUN mode (no real trades will be executed)${NC}\n"
else
    printf "${RED}Starting in LIVE mode with REAL money!${NC}\n"
    printf "${RED}Press Ctrl+C within 5 seconds to cancel...${NC}\n"
    sleep 5
fi

# Start FreqTrade with the ATRSignal strategy
printf "${GREEN}Starting FreqTrade...${NC}\n"
freqtrade trade --config "user_data/config/${CONFIG_FILE}" --strategy ${STRATEGY} 