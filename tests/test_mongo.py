# test_mongo.py
from inter_agent_mongo import inter_agent_store_from_env

def run_db_test():
    print("Connecting to MongoDB Cloud...")
    try:
        # Initialize the store using your new environment variables
        mongo_store = inter_agent_store_from_env()
        
        # Create a dummy message
        test_message = {
            "id": "test-mongo-001",
            "sender": "System",
            "recipient": "TestAgent",
            "task_type": "PING_DATABASE",
            "status": "pending"
        }
        
        print("Sending test message to cloud...")
        result = mongo_store.record_and_enqueue(test_message)
        print(f"Insert Result: {result}")
        
        print("Retrieving message from cloud inbox...")
        retrieved = mongo_store.pop_next_for_recipient("TestAgent")
        print(f"Retrieved: {retrieved.get('id') if retrieved else 'None'}")
        
        print("Cleaning up connection...")
        mongo_store.close()
        print("Test completely successful!")
        
    except Exception as e:
        print(f"\n[ERROR] Connection failed: {e}")
        print("Did you remember to whitelist your IP in MongoDB Atlas?")

if __name__ == "__main__":
    run_db_test()