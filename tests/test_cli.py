import argparse
import sys

class MockCEOAgent:
    """A placeholder to ensure this script runs out of the box."""
    def execute_reasoning_loop(self, message):
        # Simulate processing time or LLM call here
        return f"Acknowledged. I have analyzed the input: '{message}' and initiated the business cycle."

def main():
    parser = argparse.ArgumentParser(description="CLI to test the CEO Agent reasoning loop.")
    parser.add_argument(
        "message", 
        type=str, 
        nargs="?", # Makes it optional so we can use interactive mode
        help="The test message, goal, or override to send to the CEO Agent."
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run the CLI in a continuous interactive chat loop."
    )

    args = parser.parse_args()

    # Initialize the agent
    print("System: Initializing CEO Agent...")
    print("-" * 50)
    
    # Replace MockCEOAgent() with your actual agent instantiation
    agent = MockCEOAgent() 

    # Mode 1: Interactive Loop
    if args.interactive:
        print("System: Interactive mode active. Type 'exit' or 'quit' to stop.")
        while True:
            try:
                user_input = input("\nUser -> ")
                if user_input.lower() in ['exit', 'quit']:
                    print("System: Shutting down.")
                    break
                if not user_input.strip():
                    continue
                
                print("CEO  -> Thinking...")
                response = agent.execute_reasoning_loop(user_input)
                print(f"CEO  -> {response}")
                
            except KeyboardInterrupt:
                print("\nSystem: Force quit detected. Shutting down.")
                sys.exit(0)

    # Mode 2: Single-shot CLI execution
    elif args.message:
        print(f"User -> {args.message}")
        print("CEO  -> Thinking...")
        response = agent.execute_reasoning_loop(args.message)
        print(f"CEO  -> {response}")
        print("-" * 50)

    # Fallback: No arguments provided
    else:
        parser.print_help()

if __name__ == "__main__":
    main()


#Run with: "python test_agent.py" -i or "python test_agent.py "Launch new SaaS product in Q3""
#Ran from terminal.
