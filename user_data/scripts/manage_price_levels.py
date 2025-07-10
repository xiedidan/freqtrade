#!/usr/bin/env python3
"""
Command-line utility to manage price levels for ATRLevelSignal strategy
"""
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

# Append freqtrade directory to path
sys.path.append(str(Path(__file__).parents[2]))

from freqtrade.persistence.models import init_db
from user_data.strategies.atr_level_signal import ATRLevelSignal, LevelDirection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("manage_price_levels")

def init_database(config_file: str = None) -> bool:
    """Initialize database connection"""
    try:
        # Try to get database URL from config
        db_url = None
        if config_file:
            with open(config_file, 'r') as f:
                config = json.load(f)
                db_url = config.get('db_url')
        
        # Initialize the database
        ATRLevelSignal.init_db_session()
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False

def list_levels(pair: Optional[str] = None, json_output: bool = False) -> None:
    """List all active price levels"""
    levels = ATRLevelSignal.get_price_levels(pair)
    
    if json_output:
        print(json.dumps(levels, indent=2))
        return
    
    if not levels:
        print("No active price levels found.")
        return
    
    print(f"Found {len(levels)} active price levels:")
    print("-" * 80)
    print(f"{'ID':<5} {'Pair':<15} {'Level':<15} {'Direction':<10} {'Confirm Close':<15} {'Created At':<25}")
    print("-" * 80)
    
    for level in levels:
        print(f"{level['id']:<5} {level['pair']:<15} {level['level']:<15.6f} {level['direction']:<10} {'Yes' if level['confirm_close'] else 'No':<15} {level['created_at']:<25}")

def add_level(pair: str, level: float, direction: str = "both", confirm_close: bool = False) -> None:
    """Add a new price level"""
    if direction not in [d.value for d in LevelDirection]:
        print(f"Error: Direction must be one of: {', '.join([d.value for d in LevelDirection])}")
        return
    
    result = ATRLevelSignal.add_price_level(pair, level, direction, confirm_close)
    
    if "error" in result:
        print(f"Error adding level: {result['error']}")
    else:
        print(f"Successfully added price level {level} for {pair}")
        print(f"ID: {result['id']}")
        print(f"Direction: {result['direction']}")
        print(f"Confirm Close: {'Yes' if result['confirm_close'] else 'No'}")
        print(f"Created At: {result['created_at']}")

def delete_level(level_id: int) -> None:
    """Delete a price level"""
    result = ATRLevelSignal.delete_price_level(level_id)
    
    if result.get("success", False):
        print(f"Successfully deleted price level with ID {level_id}")
    else:
        print(f"Error deleting level: {result.get('error', 'Unknown error')}")

def update_level(level_id: int, level: Optional[float] = None, 
                direction: Optional[str] = None, confirm_close: Optional[bool] = None) -> None:
    """Update an existing price level"""
    if direction is not None and direction not in [d.value for d in LevelDirection]:
        print(f"Error: Direction must be one of: {', '.join([d.value for d in LevelDirection])}")
        return
    
    result = ATRLevelSignal.update_price_level(level_id, level, direction, confirm_close)
    
    if result.get("success", False):
        print(f"Successfully updated price level with ID {level_id}")
        level_data = result.get("level", {})
        print(f"Pair: {level_data.get('pair')}")
        print(f"Level: {level_data.get('level')}")
        print(f"Direction: {level_data.get('direction')}")
        print(f"Confirm Close: {'Yes' if level_data.get('confirm_close') else 'No'}")
    else:
        print(f"Error updating level: {result.get('error', 'Unknown error')}")

def main() -> None:
    """Main function"""
    parser = argparse.ArgumentParser(description='Manage price levels for ATRLevelSignal strategy')
    parser.add_argument('--config', type=str, help='Path to Freqtrade config file')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all active price levels')
    list_parser.add_argument('--pair', type=str, help='Filter by trading pair')
    list_parser.add_argument('--json', action='store_true', help='Output in JSON format')
    
    # Add command
    add_parser = subparsers.add_parser('add', help='Add a new price level')
    add_parser.add_argument('--pair', type=str, required=True, help='Trading pair (e.g. BTC/USDT)')
    add_parser.add_argument('--level', type=float, required=True, help='Price level value')
    add_parser.add_argument('--direction', type=str, default='both', choices=['up', 'down', 'both'], 
                           help='Direction to monitor (up/down/both)')
    add_parser.add_argument('--confirm-close', action='store_true', 
                           help='Require candle close confirmation')
    
    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete a price level')
    delete_parser.add_argument('--id', type=int, required=True, help='ID of the price level to delete')
    
    # Update command
    update_parser = subparsers.add_parser('update', help='Update an existing price level')
    update_parser.add_argument('--id', type=int, required=True, help='ID of the price level to update')
    update_parser.add_argument('--level', type=float, help='New price level value')
    update_parser.add_argument('--direction', type=str, choices=['up', 'down', 'both'], 
                              help='New direction')
    update_parser.add_argument('--confirm-close', type=bool, 
                              help='New confirm close value')
    
    args = parser.parse_args()
    
    # Initialize database
    if not init_database(args.config):
        print("Failed to initialize database. Exiting.")
        sys.exit(1)
    
    # Execute command
    if args.command == 'list':
        list_levels(args.pair, args.json)
    elif args.command == 'add':
        add_level(args.pair, args.level, args.direction, args.confirm_close)
    elif args.command == 'delete':
        delete_level(args.id)
    elif args.command == 'update':
        update_level(args.id, args.level, args.direction, args.confirm_close)
    else:
        parser.print_help()

if __name__ == '__main__':
    main() 