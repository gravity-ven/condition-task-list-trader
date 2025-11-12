#!/usr/bin/env python3
"""
Condition Task List Trader
An autonomous trading system that waits for user-provided conditions to be met
before executing trades.
"""

import time
import threading
from condition_parser import ConditionParser
from conditions_matcher import ConditionsMatcher, MarketData
from market_data_simulator import MarketDataSimulator
from dashboard import TaskDashboard
from trade_executor import TradeExecutor
from broker_integrations import BrokerManager
from conversation_manager import conversation_manager

def main():
    print("🚀 CONDITION TASK LIST TRADER")
    print("=" * 50)
    print("Waiting for your 'Condition Task List'...")
    print("Example: 'Condition Task List: RSI < 30, price above 50-day SMA, volume spike'")
    print("Type 'quit' to exit, 'demo' to see a demo scenario")
    print("Type 'export' to download conversation archive")
    print("=" * 50)
    
    # Start conversation archiving
    conversation_manager.start_conversation("Trading System Session")
    
    # Create components
    parser = ConditionParser()
    matcher = ConditionsMatcher()
    executor = TradeExecutor()
    
    # Broker integration is now built into TradeExecutor
    # The executor will automatically connect to available brokers
    print(f"📊 Trade executor initialized")
    if executor.using_real_broker:
        broker_name = type(executor.broker_manager.active_broker).__name__.replace('Broker', '')
        print(f"🎯 Connected to {broker_name} for real trade execution")
    else:
        print("⚠️  No broker connected - using simulation mode")
    
    # Setup trade execution callback
    def on_trade_executed(symbol: str, conditions):
        print("\n🎯 ALL CONDITIONS MET! EXECUTING TRADE:")
        print(f"   Symbol: {symbol}")
        print("   Conditions met:")
        for condition in conditions:
            status = "✅" if condition.completed else "❌"
            print(f"   {status} {condition.description}")
        print("   TRADE EXECUTED! 🚀")
        
        # Get market data for execution
        market_data = matcher.market_data.get(symbol)
        if market_data:
            execution = executor.execute_trade(symbol, market_data, conditions)
            if execution:
                trade_type = "REAL" if executor.using_real_broker else "SIMULATED"
                print(f"🚀 {trade_type} trade executed successfully!")
        else:
            print("❌ No market data available for execution")
    
    def on_conditions_updated(conditions):
        # Display current status
        completed = sum(1 for c in conditions if c.completed)
        total = len(conditions)
        print(f"\\rStatus: {completed}/{total} conditions met", end="", flush=True)
    
    matcher.register_trade_callback(on_trade_executed)
    matcher.register_update_callback(on_conditions_updated)
    
    # Start the matcher engine
    matcher.start_matching()
    
    # Create market data simulator
    simulator = MarketDataSimulator("AAPL")
    
    # Market data update callback
    def update_market_data(symbol: str, data: MarketData):
        matcher.update_market_data(symbol, data)
    
    # Start simulation in background thread
    simulation_thread = threading.Thread(
        target=simulator.simulate_data_stream, 
        args=(update_market_data, 0.1),
        daemon=True
    )
    simulation_thread.start()
    
    try:
        while True:
            user_input = input("\\n\\n> ").strip()
            
            # Archive conversation turn
            ai_response = ""
            context = {}
            
            if user_input.lower() == 'quit':
                ai_response = "Shutting down system. All conversations archived for learning."
                conversation_manager.add_conversation_turn(user_input, ai_response)
                break
            
            elif user_input.lower() == 'demo':
                ai_response = "Running demo scenario to show condition task list functionality..."
                conversation_manager.add_conversation_turn(user_input, ai_response, {'demo_mode': True})
                run_demo_scenario(matcher, simulator, update_market_data)
                continue
            
            elif user_input.lower() == 'export':
                ai_response = "Exporting conversation archive..."
                conversation_manager.add_conversation_turn(user_input, ai_response)
                
                insights = conversation_manager.get_conversation_insights()
                print(f"\\n📊 Conversation Insights:")
                if insights.get('conversation_stats'):
                    stats = insights['conversation_stats']
                    print(f"   Total sessions: {stats.get('total_conversations', 0)}")
                    print(f"   Total turns: {stats.get('total_turns', 0)}")
                    print(f"   Avg turns per session: {stats.get('avg_turns_per_conversation', 0):.1f}")
                
                print("\\n💬 Exporting full conversation archive...")
                conversation_manager.export_conversations()
                continue
            
            else:
                # Get relevant context from previous conversations
                relevant_context = conversation_manager.get_relevant_context(user_input)
                
                # Parse and add conditions
                conditions = parser.parse_task_list(user_input)
                if conditions:
                    ai_response = f"Added {len(conditions)} tasks to monitor. Starting real-time evaluation..."
                    
                    print(f"\\n📋 Added {len(conditions)} tasks:")
                    for condition in conditions:
                        print(f"   [⏳] {task_description(condition)}")
                    
                    # Clear existing conditions and add new ones
                    matcher.conditions.clear()
                    matcher.add_conditions(conditions)
                    print(f"\\n🔄 Monitoring conditions for AAPL...")
                    
                    # Enhanced context for this turn
                    context = {
                        'conditions_added': len(conditions),
                        'similar_past_queries': len(relevant_context.get('similar_conversations', [])),
                        'applicable_patterns': relevant_context.get('recent_patterns', [])
                    }
                    
                else:
                    ai_response = "Could not parse conditions. Try: 'Condition Task List: RSI < 30, price > 150'"
                    context = {'parsing_failed': True}
    
            # Archive this conversation turn
            conversation_manager.add_conversation_turn(user_input, ai_response, context)
    
    except KeyboardInterrupt:
        conversation_manager.end_conversation({'reason': 'keyboard_interrupt', 'total_turns': conversation_manager.turn_count})
        pass
    finally:
        matcher.stop_matching()
        simulator.stop_simulation()
        conversation_manager.shutdown()
        print("\\n👋 Goodbye!")

def task_description(condition) -> str:
    """Create human-readable task description"""
    return f"{condition.indicator} {condition.operator} {condition.value}"

def run_demo_scenario(matcher: ConditionsMatcher, simulator: MarketDataSimulator, update_callback):
    """Run a demo scenario showing the system in action"""
    print("\\n🎭 DEMO MODE: Setting up a scenario...")
    
    # Create demo conditions
    parser = ConditionParser()
    demo_input = "Condition Task List: RSI < 30, price < 150, volume > 2000000"
    conditions = parser.parse_task_list(demo_input)
    
    matcher.conditions.clear()
    matcher.add_conditions(conditions)
    
    print(f"\\n📋 Created demo tasks:")
    for condition in conditions:
        print(f"   [⏳] {task_description(condition)}")
    
    print("\\n🎬 Simulating market conditions...")
    
    # Simulate the market meeting conditions one by one
    scenarios = [
        ("normal", "Normal market..."),
        ("oversold", "RSI dropping below 30..."),
        ("volume_spike", "Volume spiking..."),
        ("price_drop", "Price dropping below 150...")
    ]
    
    for scenario, description in scenarios:
        print(f"\\n{description}")
        data = simulator.create_custom_scenario(scenario)
        update_callback(simulator.symbol, data)
        time.sleep(2)
        
        # Show current status
        completed = sum(1 for c in matcher.conditions if c.completed)
        total = len(matcher.conditions)
        print(f"   Status: {completed}/{total} conditions met")
        
        for condition in matcher.conditions:
            status = "✅" if condition.completed else "⏳"
            print(f"   {status} {task_description(condition)}")

if __name__ == "__main__":
    main()
